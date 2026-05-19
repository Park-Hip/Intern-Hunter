from src.flows.ingestion_flow import job_ingestion_flow

def deploy():
    print("Building and serving deployment for job_ingestion_flow...")
    job_ingestion_flow.serve(
        name="daily-job-ingestion",
        cron="0 2 * * *", # Run daily at 2:00 AM
        tags=["etl", "daily"],
        parameters={"limit": 50}
    )

if __name__ == "__main__":
    deploy()
