import os
import json
from datetime import date
import boto3


class R2Storage:
    def __init__(self):
        self.bucket = os.getenv("R2_BUCKET")
        self.endpoint = os.getenv("R2_ENDPOINT_URL")
        self.access_key = os.getenv("R2_ACCESS_KEY_ID")
        self.secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

        self.enabled = all([
            self.bucket,
            self.endpoint,
            self.access_key,
            self.secret_key
        ])

        if self.enabled:
            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name="auto"
            )

    def save_daily_trends(self, trends: list):
        """
        trends = [
          { "name": "...", "intensity": "...", "reason": "..." }
        ]
        """
        if not self.enabled:
            return

        today = date.today().isoformat()
        key = f"{today}.json"

        body = json.dumps({
            "date": today,
            "trends": trends
        }, ensure_ascii=False, indent=2)

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json"
        )

    def load_recent_trends(self, days=5):
        if not self.enabled:
            return []

        from datetime import timedelta

        results = []
        for i in range(days):
            d = (date.today() - timedelta(days=i)).isoformat()
            key = f"{d}.json"
            try:
                obj = self.client.get_object(
                    Bucket=self.bucket,
                    Key=key
                )
                results.append(
                    json.loads(obj["Body"].read())
                )
            except Exception:
                continue

        return results