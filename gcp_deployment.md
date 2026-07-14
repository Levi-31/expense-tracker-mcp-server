# Google Cloud Platform (GCP) Deployment Guide

This guide covers how to deploy the Async Expense Tracker MCP Server to Google Cloud Platform (GCP).

The two recommended deployment options are:
* **Option A: Google Cloud Run (Recommended)** - Serverless, auto-scaling, completely managed HTTPS endpoint. Ideal if you are using a managed database (e.g. Neon PostgreSQL).
* **Option B: Google Compute Engine VM** - A virtual machine running Docker Compose. Useful if you want to host both the MCP server and a PostgreSQL database on the same VM.

---

## Option A: Deploying on Google Cloud Run (Serverless)

Cloud Run is the easiest and most cost-effective way to run containerized MCP servers. It handles provisioning, scaling, and HTTPS certificates automatically.

### Step 1: Install & Initialize Google Cloud CLI
If you haven't already, install the `gcloud` CLI on your local machine and log in:
```bash
gcloud auth login
gcloud config set project <YOUR_GCP_PROJECT_ID>
```

### Step 2: Build and Deploy to Cloud Run
Using Google Cloud Build, you can build the container image in the cloud and deploy it directly:
```bash
gcloud run deploy expense-tracker-mcp \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000
```
During the prompt, select `y` to allow unauthenticated invocations (required for MCP clients to connect).

### Step 3: Configure Environment Variables
You can add environment variables directly during deployment, or add them via the GCP Console:

**Command Line update:**
```bash
gcloud run services update expense-tracker-mcp \
  --set-env-vars="DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require,GOOGLE_CLIENT_ID=your_client_id,GOOGLE_CLIENT_SECRET=your_client_secret,GOOGLE_REDIRECT_URI=https://<your-service-url>/callback,POOL_MIN_SIZE=2,POOL_MAX_SIZE=10"
```

**Console UI update:**
1. Open the GCP Console and search for **Cloud Run**.
2. Click on `expense-tracker-mcp`.
3. Click **Edit & Deploy New Revision**.
4. Scroll down to **Variables & Secrets** under the Container tab.
5. Add Name-Value pairs:
   * `DATABASE_URL` = (Your database connection string)
   * `GOOGLE_CLIENT_ID` = (Your Google OAuth Client ID)
   * `GOOGLE_CLIENT_SECRET` = (Your Google OAuth Client Secret)
   * `GOOGLE_REDIRECT_URI` = `https://<YOUR_CLOUD_RUN_URL>/callback`
   * `PORT` = `8000`
6. Click **Deploy**.

Once deployed, Cloud Run will output a public HTTPS URL (e.g. `https://expense-tracker-mcp-xxxxxx-uc.a.run.app`).

---

## Option B: Deploying on Google Compute Engine VM (Docker Compose)

Use this method if you want to self-host both the PostgreSQL database and the MCP server on a single VM instance.

### Step 1: Create Compute Engine VM
1. Go to GCP Console -> **Compute Engine** -> **VM instances**.
2. Click **Create Instance**.
3. Choose a machine configuration (e.g. `e2-micro` or `e2-small` which are very inexpensive).
4. In the **Boot disk** section, select **Ubuntu 22.04 LTS** or **Debian 12**.
5. In the **Firewall** section, check **Allow HTTP traffic** and **Allow HTTPS traffic**.
6. Click **Create**.

### Step 2: Configure Firewall for MCP Port (8000)
By default, GCP blocks port 8000. You need to create a firewall rule:
1. Search for **VPC network** -> **Firewalls** in the GCP Console.
2. Click **Create Firewall Rule**.
3. Set the following parameters:
   * **Name**: `allow-mcp-port`
   * **Targets**: All instances in the network (or use a specific target tag)
   * **Source IPv4 ranges**: `0.0.0.0/0`
   * **Protocols and ports**: Specified protocols -> Check **TCP** -> enter `8000`.
4. Click **Create**.

### Step 3: Install Docker and Docker Compose on the VM
SSH into your instance using the GCP Console SSH button or gcloud:
```bash
gcloud compute ssh <INSTANCE_NAME> --zone=<INSTANCE_ZONE>
```
On the VM, run the following script to install Docker:
```bash
# Update repository index
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
sudo apt-get install -y docker.io

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Allow your user to run Docker without sudo
sudo usermod -aG docker $USER
exit
```
Log back in (using SSH) to apply group permissions.

### Step 4: Clone Code and Launch
1. Clone your project code onto the VM.
2. Create a `.env` file in the root directory:
   ```env
   DB_USER=postgres
   DB_PASSWORD=your_secure_password_here
   DB_NAME=expense_tracker
   ```
3. Launch containers:
   ```bash
   docker compose up -d --build
   ```
4. Verify they are running:
   ```bash
   docker compose ps
   ```
   The server is now live at `http://<VM_PUBLIC_IP>:8000/mcp`.

---

## Client Configuration

To connect your MCP client (like Claude Desktop) to the deployed server:

### For Google Cloud Run (HTTPS):
```json
"expense-tracker": {
  "command": "curl",
  "args": ["-s", "-N", "https://<YOUR_CLOUD_RUN_URL>/mcp"]
}
```

### For Compute Engine VM (HTTP):
```json
"expense-tracker": {
  "command": "curl",
  "args": ["-s", "-N", "http://<YOUR_VM_PUBLIC_IP>:8000/mcp"]
}
```

### Health Check Verification
Verify connection by querying the health endpoint:
```bash
curl https://<YOUR_DEPLOYED_ENDPOINT>/health
```
Expected output:
```json
{"status":"healthy","database":"connected"}
```
