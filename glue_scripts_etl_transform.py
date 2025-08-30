# etl_transform.py
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F, types as T

args = getResolvedOptions(sys.argv, ["JOB_NAME","INPUT_PATH","OUTPUT_PREFIX","RUN_ID"])
INPUT_PATH    = args["INPUT_PATH"]
OUTPUT_PREFIX = args["OUTPUT_PREFIX"].rstrip("/")
RUN_ID        = args["RUN_ID"]

BAD_RECORDS_PATH = f"{OUTPUT_PREFIX}/_bad_records/{RUN_ID}/"

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext); job.init(args["JOB_NAME"], args)
log = glueContext.get_logger()

def schema():
    return T.StructType([
        T.StructField("timestamp",  T.StringType(),  True),
        T.StructField("level",      T.StringType(),  True),
        T.StructField("service",    T.StringType(),  True),
        T.StructField("endpoint",   T.StringType(),  True),
        T.StructField("method",     T.StringType(),  True),
        T.StructField("status",     T.IntegerType(), True),
        T.StructField("message",    T.StringType(),  True),
        T.StructField("latency_ms", T.LongType(),    True),
        T.StructField("request_id", T.StringType(),  True),
        T.StructField("user_id",    T.StringType(),  True),
        T.StructField("ip",         T.StringType(),  True),
        T.StructField("user_agent", T.StringType(),  True),
    ])

def parse_event_time(df):
    s = F.col("timestamp").cast("string")
    df = df.withColumn(
        "ts",
        F.when(s.rlike(r"^\d{13,}$"), (s.cast("double")/1000.0))
         .when(s.rlike(r"^\d{10,12}$"), s.cast("double"))
         .otherwise(F.unix_timestamp(s))
    )
    df = df.withColumn("ts", F.when(F.col("ts").isNull(), F.current_timestamp().cast("double")).otherwise(F.col("ts")))
    return df.withColumn("event_time", F.to_timestamp(F.from_unixtime("ts")))

def quality(df):
    levels = F.array(*[F.lit(x) for x in ["INFO","WARN","ERROR","DEBUG"]])
    df = df.withColumn("level", F.upper(F.col("level")))
    df = df.withColumn("method", F.upper(F.col("method")))
    df = df.withColumn("status", F.when(F.col("status").isNull(), None).otherwise(F.col("status").cast("int")))
    df = df.filter((F.col("level").isNull()) | F.array_contains(levels, F.col("level")))
    df = df.filter((F.col("status").isNull()) | ((F.col("status") >= 100) & (F.col("status") <= 599)))
    return df

def lineage(df):
    df = df.withColumn("date", F.to_date("event_time"))
    df = df.withColumn("hour", F.date_format("event_time", "HH"))
    df = df.withColumn("source_file", F.input_file_name())
    df = df.withColumn("ingestion_time_utc", F.current_timestamp())
    concat_cols = F.concat_ws("|",
        F.coalesce(F.col("service"), F.lit("")),
        F.coalesce(F.col("endpoint"), F.lit("")),
        F.coalesce(F.col("method"), F.lit("")),
        F.coalesce(F.col("status").cast("string"), F.lit("")),
        F.coalesce(F.col("message"), F.lit("")),
        F.col("event_time").cast("string")
    )
    return df.withColumn("event_hash", F.sha2(concat_cols, 256))

def choose_cols(df):
    cols = [c for c in [
        "event_time","date","hour","level","service","endpoint","method",
        "status","message","latency_ms","request_id","user_id","ip","user_agent",
        "source_file","ingestion_time_utc","event_hash"
    ] if c in df.columns]
    for must in ["event_time","date","hour","level","service","endpoint","method","status","message","source_file","ingestion_time_utc","event_hash"]:
        if must not in cols:
            df = df.withColumn(must, F.lit(None))
            cols.append(must)
    return df.select(*cols)

try:
    df_raw = (
        spark.read
             .schema(schema())
             .option("badRecordsPath", BAD_RECORDS_PATH)
             .option("multiLine", "false")
             .json(INPUT_PATH if INPUT_PATH.endswith(("/", ".json", ".gz")) else INPUT_PATH + "/*")
    )
    cnt = df_raw.count()
    log.info(f"READ rows={cnt} from {INPUT_PATH}")
except Exception as e:
    log.error(f"READ_FAILED: {e}")
    job.commit(); raise

try:
    if df_raw.rdd.isEmpty():
        log.warn("No records; exiting.")
        job.commit(); sys.exit(0)

    df = parse_event_time(df_raw)
    df = quality(df)
    df = lineage(df)
    df = choose_cols(df)

    before = df.count()
    df = df.dropDuplicates(["event_hash"])
    after = df.count()
    log.info(f"DEDUP {before}->{after}")

    target_parts = max(1, min(64, after // 250_000 + 1))
    df = df.repartition(target_parts, "date","hour")
except Exception as e:
    log.error(f"TRANSFORM_FAILED: {e}")
    job.commit(); raise

try:
    (df.write
       .mode("append")
       .format("parquet")
       .option("compression","snappy")
       .partitionBy("date","hour")
       .save(f"{OUTPUT_PREFIX}/"))
    log.info(f"WROTE parquet to {OUTPUT_PREFIX}/")
except Exception as e:
    log.error(f"WRITE_FAILED: {e}")
    job.commit(); raise

job.commit()
log.info("SUCCESS")
