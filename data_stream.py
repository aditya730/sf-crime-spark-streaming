import logging
from pyspark.sql import SparkSession
from pyspark.sql.types import *
import pyspark.sql.functions as psf
import threading
import time

def query_progress(query):
    #This operation is thread safe and periodically tracks the progress.
    while True:
        time.sleep(10)
        print(query.lastProgress)

def run_spark_job(spark):

# TODO Create a schema for incoming resources
    schema = StructType([
        StructField("crime_id", StringType(), False),
        StructField("original_crime_type_name", StringType(), False),
        StructField("report_date", TimestampType(), True),
        StructField("call_date", TimestampType(), True),
        StructField("offense_date", TimestampType(), True),
        StructField("call_time", StringType(), True),
        StructField("call_date_time", TimestampType(), True),
        StructField("disposition", StringType(), True),
        StructField("address", StringType(), True),
        StructField("city", StringType(), True),
        StructField("state", StringType(), True),
        StructField("agency_id", StringType(), True),
        StructField("address_type", StringType(), True),
        StructField("common_location", StringType(), True)
    ])

    df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "localhost:9092") \
        .option("subscribe", "police.service.calls.v2") \
        .option('maxOffsetsPerTrigger', 10) \
        .option('stopGracefullyOnShutdown', "true") \
        .load()

    # Show schema for the incoming resources for checks
    df.printSchema()


    # TODO extract the correct column from the kafka input resources
    # Take only value and convert it to String
    kafka_df = df.selectExpr("CAST(value AS STRING)")

    service_table = kafka_df\
        .select(psf.from_json(psf.col('value'), schema).alias("DF"))\
        .select("DF.*")

    # TODO select original_crime_type_name and disposition
    distinct_table = service_table\
        .select("original_crime_type_name", "disposition")

# count the number of original crime type
    agg_df = distinct_table\
        .groupBy("original_crime_type_name")\
        .count()

    # TODO Q1. Submit a screen shot of a batch ingestion of the aggregation
    # TODO write output stream
    query = agg_df \
        .writeStream \
        .format("console") \
        .outputMode("complete") \
        .trigger(processingTime='10 seconds') \
        .option("truncate", "false") \
        .start()

    thread = threading.Thread(target = query_progress, args = [query])
    thread.start()
    # TODO attach a ProgressReporter
    query.awaitTermination()

    # TODO get the right radio code json path
    radio_code_json_filepath = "radio_code.json"
    radio_code_df = spark.read.json(radio_code_json_filepath)

    # clean up your data so that the column names match on radio_code_df and agg_df
    # we will want to join on the disposition code

    # TODO rename disposition_code column to disposition
    radio_code_df = radio_code_df.withColumnRenamed("disposition_code", "disposition")

    # TODO join on disposition column
    join_query = agg_df \
        .join(radio_code_df, col('agg_df.disposition') == col('radio_code_df.disposition'), 'left_outer')

    join_query.awaitTermination()


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    # TODO Create Spark in Standalone mode
    spark = SparkSession \
        .builder \
        .master("local[*]") \
        .appName("KafkaSparkStructuredStreaming") \
        .config("spark.ui.port", 3000) \
        .config("spark.default.parallelism", 8) \
        .config("spark.sql.shuffle.partitions", 16) \
        .getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")
    logger.info("Spark started")
    run_spark_job(spark)
    spark.stop()
