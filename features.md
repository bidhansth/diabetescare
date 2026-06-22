# DiabetesCare — Features

## Task #1: EC2 + DynamoDB (Complete)

### User Accounts
- Sign up with name, email, and password
- Log in to get a secure token that lasts 24 hours
- Passwords are hashed with bcrypt for safety
- All pages except login/signup require authentication

### Logging Health Data
- The dashboard has four big buttons for quick logging: Glucose, Meal, Medication, and Exercise
- Click any button and an inline form appears right there — enter the value, add optional notes, and save
- Each type shows the right unit automatically (mg/dL for glucose, grams for carbs, mg for medication, minutes for exercise)
- The dashboard refreshes instantly after saving so you see updated counts

### Dashboard
- Welcome message with your name
- Four stat cards showing how many entries you logged today of each type
- Latest glucose reading displayed prominently with color coding (green for normal, yellow for borderline, red for high/low)
- Recent entries table showing everything you logged today
- Quick-log buttons right on the dashboard — no separate page needed

### History Page
- Scroll through all your past entries, newest first
- Filter by entry type (glucose, meal, medication, or exercise)
- Filter by date range with from/to date pickers
- Click "Load More" to paginate through older entries

### Alerts
- When you log a glucose reading below 70 or above 180, an alert is automatically created
- The alerts page shows all triggered alerts with their severity level (high/low)
- Each alert shows the glucose value, timestamp, and acknowledgment status

### How Data is Stored
- A single DynamoDB table called `DiabetesCare` stores everything
- User profiles, log entries, and alert records each have their own structured key pattern
- Numeric values are handled precisely to work correctly with DynamoDB

### Deployment
- The app runs on EC2 using FastAPI and uvicorn on port 8000 (no nginx needed)
- A systemd service keeps the app running and restarts it if it crashes
- Configuration comes from environment variables (AWS region, table name, JWT secret)
- EC2 instance has an IAM role with permissions to access DynamoDB

### Frontend Design
- Responsive layout using Bootstrap 5 — works on phones and desktops
- Medical-themed color palette
- Loading spinners shown while data is being fetched
- Clear error messages when something goes wrong
- Consistent navigation bar across all pages

---

## Task #2: Serverless + Monitoring (Planned)

### Microservices with Lambda

**Alert Service**
- When the EC2 app detects an out-of-range glucose reading, it calls the Alert Service through API Gateway instead of handling it directly
- The service checks the value against thresholds (low < 70, high > 180)
- For out-of-range readings, it publishes a message to an SNS topic
- SNS sends an email alert to the user
- The same alert is also enqueued to SQS for an audit trail

**Export Service**
- From the dashboard or history page, users can click "Export" to generate a CSV report
- The Export Service query's DynamoDB for the user's entries
- It generates a CSV file with columns: Timestamp, Type, Value, Unit, Notes
- The file is uploaded to S3 and the user gets a download link (valid for 1 hour)

### Notifications (SNS)
- An SNS topic called `diabetescare-alerts` handles all alert notifications
- Users confirm their email subscription via a confirmation link
- Emails are sent automatically whenever a glucose reading is out of range

### Audit Trail (SQS)
- Every triggered alert is also recorded in an SQS queue
- This provides an audit trail that can be processed asynchronously
- Messages stay in the queue for up to 4 days

### File Storage (S3)
- Exported CSV files are stored in an S3 bucket
- Files are organized by user ID
- The bucket is not publicly accessible — downloads use temporary pre-signed URLs
- Encryption is enabled at rest

### Monitoring with CloudWatch
- A custom dashboard shows key metrics for all services:
  - **EC2**: CPU usage, network traffic, and instance health
  - **DynamoDB**: Read/write capacity and throttled requests
  - **Lambda**: How many times each function runs, error count, and execution duration
  - **API Gateway**: Request volume, response latency, and error rates
  - **SNS**: Messages published and delivered
  - **SQS**: How many messages are waiting in the queue
- CloudWatch Logs capture output from Lambda functions
- Alarms can be set up to notify when something needs attention (e.g., high CPU, Lambda errors)

### Distributed Tracing with X-Ray
- X-Ray traces requests as they travel from the browser through EC2, API Gateway, Lambda, and on to SNS/SQS/S3
- The service map provides a visual diagram of how all the services connect
- Tracing is enabled on Lambda functions, API Gateway, and the EC2 app itself

---

## Services Used Across Both Tasks

| Service | What It Does | When |
|---|---|---|
| EC2 | Runs the main application server | Task #1 |
| DynamoDB | Stores all user data and entries | Task #1 |
| Lambda | Runs microservices for alerts and exports | Task #2 |
| API Gateway | Routes requests to Lambda functions | Task #2 |
| SNS | Sends email notifications for alerts | Task #2 |
| SQS | Queues alert messages for audit/history | Task #2 |
| S3 | Stores exported CSV files | Task #2 |
| CloudWatch | Metrics dashboard and log monitoring | Task #2 |
| X-Ray | Traces requests across services | Task #2 |
| IAM | Manages permissions for all services | Both |
