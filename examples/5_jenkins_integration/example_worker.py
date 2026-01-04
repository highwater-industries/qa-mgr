"""
Example Worker Implementation

This is a complete example of a worker that can execute jobs from quarion.
This worker polls for jobs, executes them, and reports results.
"""

import asyncio
import httpx
import os
from datetime import datetime


class QuarionWorker:
    """
    Worker that polls quarion for jobs and executes them.
    
    This replaces Jenkins agents/lockable resources with a more flexible system.
    """
    
    def __init__(
        self,
        quarion_url: str,
        workspace_id: str,
        workspace_token: str,
        worker_name: str,
        worker_type: str,
        endpoint_url: str,
        capabilities: dict = None,
        max_concurrent_jobs: int = 1,
        tags: list[str] = None
    ):
        self.quarion_url = quarion_url.rstrip('/')
        self.workspace_id = workspace_id
        self.workspace_token = workspace_token
        self.worker_name = worker_name
        self.worker_type = worker_type
        self.endpoint_url = endpoint_url
        self.capabilities = capabilities or {}
        self.max_concurrent_jobs = max_concurrent_jobs
        self.tags = tags or []
        
        self.worker_api_key = None
        self.running = False
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def register(self):
        """Register worker with quarion."""
        print(f"Registering worker '{self.worker_name}'...")
        
        response = await self.client.post(
            f"{self.quarion_url}/quarion/api/v1/workspaces/{self.workspace_id}/workers/register",
            headers={"Authorization": f"Bearer {self.workspace_token}"},
            json={
                "name": self.worker_name,
                "worker_type": self.worker_type,
                "endpoint_url": self.endpoint_url,
                "capabilities": self.capabilities,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "tags": self.tags
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Registration failed: {response.text}")
        
        data = response.json()
        self.worker_api_key = data["api_key"]
        
        print(f"✅ Worker registered with ID: {data['worker_id']}")
        print(f"⚠️  Store API key securely: {self.worker_api_key[:20]}...")
    
    async def heartbeat_loop(self):
        """Send heartbeat every 60 seconds."""
        while self.running:
            try:
                await self.client.post(
                    f"{self.quarion_url}/quarion/api/v1/workspaces/{self.workspace_id}/workers/heartbeat",
                    headers={"Authorization": f"Bearer {self.worker_api_key}"}
                )
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❤️  Heartbeat sent")
                
            except Exception as e:
                print(f"❌ Heartbeat failed: {e}")
            
            await asyncio.sleep(60)
    
    async def job_polling_loop(self):
        """Poll for jobs and execute them."""
        while self.running:
            try:
                # Try to claim a job
                response = await self.client.get(
                    f"{self.quarion_url}/quarion/api/v1/workspaces/{self.workspace_id}/workers/next-job",
                    headers={"Authorization": f"Bearer {self.worker_api_key}"}
                )
                
                if response.status_code == 200:
                    job = response.json()
                    print(f"\n📥 Claimed job: {job['job_id']}")
                    print(f"   Type: {job['job_type']}")
                    
                    # Execute job
                    await self.execute_job(job)
                    
                elif response.status_code == 404:
                    # No jobs available
                    await asyncio.sleep(10)
                    
                else:
                    print(f"❌ Error claiming job: {response.status_code} - {response.text}")
                    await asyncio.sleep(30)
                    
            except Exception as e:
                print(f"❌ Job polling error: {e}")
                await asyncio.sleep(30)
    
    async def execute_job(self, job: dict):
        """
        Execute a job and report results.
        
        This is where you implement your job execution logic.
        """
        job_id = job["job_id"]
        job_type = job["job_type"]
        payload = job["payload"]
        
        print(f"🔨 Executing job {job_id}...")
        print(f"   Payload: {payload}")
        
        start_time = datetime.now()
        
        try:
            # Execute the job based on type
            if job_type == "test_execution":
                result = await self.execute_tests(payload)
            elif job_type == "build":
                result = await self.execute_build(payload)
            else:
                result = await self.execute_generic(payload)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            print(f"✅ Job completed in {execution_time:.1f}s")
            
            # Report success
            await self.client.post(
                f"{self.quarion_url}/quarion/api/v1/workspaces/{self.workspace_id}/workers/jobs/{job_id}/complete",
                headers={"Authorization": f"Bearer {self.worker_api_key}"},
                json={
                    "result": result,
                    "success": True
                }
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            print(f"❌ Job failed after {execution_time:.1f}s: {e}")
            
            # Report failure
            await self.client.post(
                f"{self.quarion_url}/quarion/api/v1/workspaces/{self.workspace_id}/workers/jobs/{job_id}/complete",
                headers={"Authorization": f"Bearer {self.worker_api_key}"},
                json={
                    "result": {"error": str(e)},
                    "success": False,
                    "error_message": str(e)
                }
            )
    
    async def execute_tests(self, payload: dict) -> dict:
        """
        Execute tests based on payload.
        
        This is a placeholder - implement your actual test execution logic here.
        """
        # Example: Run pytest
        print("   Running tests...")
        
        # Simulate test execution
        await asyncio.sleep(5)
        
        # Return test results
        return {
            "tests_run": 10,
            "passed": 8,
            "failed": 2,
            "duration_seconds": 5.0,
            "jenkins_job": payload.get("jenkins_job"),
            "build_number": payload.get("build_number")
        }
    
    async def execute_build(self, payload: dict) -> dict:
        """Execute build job."""
        print("   Running build...")
        await asyncio.sleep(3)
        
        return {
            "build_status": "success",
            "artifacts": ["app.zip"],
            "duration_seconds": 3.0
        }
    
    async def execute_generic(self, payload: dict) -> dict:
        """Execute generic job."""
        action = payload.get("action", "unknown")
        print(f"   Executing action: {action}")
        
        await asyncio.sleep(2)
        
        return {
            "action": action,
            "status": "completed",
            "duration_seconds": 2.0
        }
    
    async def start(self):
        """Start the worker."""
        print(f"\n🚀 Starting Quarion Worker")
        print(f"   Name: {self.worker_name}")
        print(f"   Type: {self.worker_type}")
        print(f"   URL: {self.quarion_url}")
        print()
        
        # Register with quarion
        await self.register()
        
        self.running = True
        
        # Start heartbeat and polling loops
        print("\n📡 Starting worker loops...")
        await asyncio.gather(
            self.heartbeat_loop(),
            self.job_polling_loop()
        )
    
    async def stop(self):
        """Stop the worker gracefully."""
        print("\n🛑 Stopping worker...")
        self.running = False
        
        # Unregister
        try:
            await self.client.delete(
                f"{self.quarion_url}/quarion/api/v1/workspaces/{self.workspace_id}/workers/unregister",
                headers={"Authorization": f"Bearer {self.worker_api_key}"}
            )
            print("✅ Worker unregistered")
        except Exception as e:
            print(f"⚠️  Unregister failed: {e}")
        
        await self.client.aclose()


# Example usage
async def main():
    # Configuration (use environment variables in production)
    worker = QuarionWorker(
        quarion_url=os.getenv("QUARION_URL", "http://localhost:8000"),
        workspace_id=os.getenv("WORKSPACE_ID", "your-workspace-id"),
        workspace_token=os.getenv("WORKSPACE_TOKEN", "your-workspace-token"),
        worker_name=os.getenv("WORKER_NAME", "worker-01"),
        worker_type=os.getenv("WORKER_TYPE", "selenium"),
        endpoint_url=os.getenv("WORKER_ENDPOINT", "http://worker-01:8080"),
        capabilities={
            "browsers": ["chrome", "firefox"],
            "os": "linux",
            "selenium_version": "4.0"
        },
        max_concurrent_jobs=2,
        tags=["production", "linux"]
    )
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
