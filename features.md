# DiabetesCare — Features

## Task #1: EC2 + DynamoDB (Implemented)

### User Authentication & Accounts
- Sign up with name (letters/spaces only), email, and password (min 6 chars, must have uppercase, number, special char)
- Log in to get a JWT token that lasts 24 hours — stored in localStorage
- Passwords are hashed with bcrypt for safety
- All pages except landing/login/signup require authentication
- 401 responses auto-redirect to the landing page
- Two roles: `user` and `admin`
- Auth redirect logic: admins go to admin panel, regular users go to dashboard; already-logged-in users skip the landing page
- Logout button on all authenticated pages clears localStorage and redirects to landing page
- Field-level validation error messages on signup (inline errors for name, email, password fields)

### Dashboard
- Welcome message personalized with the user's name
- Four stat cards showing today's entry counts for Glucose, Meals, Medications, and Exercise
- Latest glucose reading displayed prominently with color coding:
  - Green (< 140): normal
  - Yellow (140–180): borderline
  - Red (< 70 or > 180): out of range
- Recent entries table showing everything logged today with time, type badge, value, and notes
- Quick-log buttons right on the dashboard — click any to reveal an inline form
- Dashboard refreshes instantly after saving so updated counts appear
- Medications can be added or deleted on the fly via a modal
- Computed dosage calculator: medication quick-log has a quantity stepper (+/- buttons, 0.5 step) that auto-computes total dosage in real-time

### Health Data Logging
- Four entry types: glucose (mg/dL), meal (carbs in grams), medication (linked to saved medications with dosage computation), exercise (minutes)
- Each type shows the appropriate unit automatically
- All fields include a date/time picker (defaults to now) and optional notes
- Dedicated log-entry page also available for full-screen logging
- Validation: type must be one of the four, value must be positive
- Medication entries can link to a saved medication (auto-fills medication name)
- Success message with auto-redirect: "Entry saved successfully!" shown, then redirects to dashboard after 1.5 seconds
- Value input and submit button disabled until user selects an entry type

### History & Trends
- Scroll through all past entries sorted newest first
- Filter by entry type (glucose, meal, medication, or exercise)
- Filter by date range with from/to date pickers
- Click "Load More" to paginate through older entries (50 per page)
- Glucose trend chart rendered with Chart.js — data points are color-coded (green/yellow/red based on value ranges)
- History table rows also color-code glucose values with the same green/yellow/red scheme

### Alerts
- Automatic triggering: when a glucose entry is below 70 (low) or above 180 (high), an alert record is created
- Alerts page shows all triggered alerts with severity level badges (high/danger or low/warning)
- Each alert shows the glucose value, timestamp, and acknowledgment status

### Medications Management
- CRUD for user's personal medications (name + dosage, e.g. "Metformin 500mg")
- Used by the dashboard medication quick-log for automatic dosage calculations
- Medications can be added or removed from the dashboard modal

### Educational Resources
- Admin uploads files (PDF, images, videos, Word docs) via multipart form
- File type validation: whitelist of allowed MIME types
- Size limit: 50 MB maximum
- Download tracking — each resource has a download counter that increments on download
- Any authenticated user can download resources (supports Bearer token header or query parameter token for direct links)
- Resource listing shows name, type icon (emoji by file type), file size (human-readable B/KB/MB/GB), upload date, description, and download link
- Resource description field (optional) displayed below name

### Community Forum
- Topics: admin-managed discussion categories (Nutrition & Diet, Medication, Exercise, etc.)
- Topic filter dropdown on forum page to filter posts by topic
- Posts: users create posts under topics with title and body
- Post title max length: 200 characters enforced on input
- Threaded comments: nested comments with replies supported to any depth
- Reply-to-reply UI: visual indentation, "Replying to [user]" info bar, cancel reply button
- Comment tree rendering with recursive indentation for visual threading
- Post/comment deletion: authors and admins can delete (cascade deletes replies), with browser confirm() dialog
- "Back to Forum" breadcrumb navigation on post detail page
- Reporting system: dedicated Bootstrap modal with reason textarea for reporting posts or comments
- Admin moderation: admins view all reports, filter by status (pending/resolved/dismissed), and resolve or dismiss them
- Pagination with limit-based cursor using LastEvaluatedKey

### Admin Panel
- Five management tabs (lazy-loaded on click):
  1. **Resources**: Upload and delete educational resource files
  2. **Carousel**: Upload, delete, and reorder carousel slide images (up/down arrow buttons) with thumbnail previews
  3. **Reports**: View and moderate user reports (resolve/dismiss) with status filtering
  4. **Topics**: Create and delete forum discussion topics
  5. **Users**: List all users, promote users to admin role
- Delete confirmation dialogs (browser confirm()) for all destructive actions
- Admin users are auto-redirected to the admin panel on login
- Admin-specific darker navbar (`#1a3a3a`) vs regular teal
- Storage health check warning if using local storage instead of S3

### Landing Page
- Carousel: admin uploads JPEG/PNG/GIF/WebP images (max 10 MB each, separate file-type whitelist) with optional captions
- Auto-ordering: new slides are automatically positioned at the end
- Reordering: admin can move slides up/down via dedicated API and database logic
- Bootstrap carousel with fade transition
- Placeholder slide: fallback with "DiabetesCare / Track. Manage. Thrive." text when no images uploaded
- Responsive display across device sizes
- Feature cards: 8 icon cards highlighting key functionality (Glucose Tracking, Meal Logging, Medications, Exercise, Dashboard, Alerts, Community Forum, Resources)

### Data Architecture (DynamoDB Single-Table Design)
- A single DynamoDB table called `DiabetesCare` stores everything
- Composite primary key (PK + SK) pattern for all entities:
  - User profiles: `USER#{id}` / `PROFILE`
  - Health entries: `USER#{id}` / `ENTRY#{timestamp}`
  - Medications: `USER#{id}` / `MED#{uuid}`
  - Alerts: `USER#{id}` / `ALERT#{timestamp}`
  - Resources: `RESOURCES` / `RES#{uuid}`
  - Topics: `TOPICS` / `TOP#{uuid}`
  - Posts: `POST#{uuid}` / `META`
  - Comments: `POST#{uuid}` / `COMMENT#{ts}#{uuid}`
  - Reports: `REPORTS` / `REPORT#{ts}#{uuid}`
  - Carousel slides: `CAROUSEL` / `SLIDE#{position}#{uuid}`
- Numeric values are handled precisely for correct DynamoDB operations

### File Storage
- Local filesystem storage for development (under `local-storage/`)
- Amazon S3 storage for production with pre-signed URLs
- Separate S3 bucket configuration for carousel images (with 24-hour presigned URLs) vs resources
- Storage backend is configurable via environment variables
- Supports carousel images and educational resources
- File type validation on upload: MIME type checked against whitelist
- Empty parent directory cleanup after file deletion in local storage

### Deployment & Infrastructure
- FastAPI application served with uvicorn on port 8000
- Local development: DynamoDB Local (via Docker or moto, auto-detected) with seed data script
- One-command local dev server (`run-local.sh`): auto-starts DynamoDB, creates table, seeds data, launches uvicorn with hot reload
- Seed data script: creates demo user (`demo@example.com`), admin user (`admin@diabetescare.com`), sample medications, 30 days of realistic historical data, sample resources, and forum topics
- EC2 deployment: automated script installs dependencies, creates systemd service
- Configuration via environment variables (AWS region, table name, JWT secret, storage backend, S3 buckets)
- EC2 instance has an IAM role with permissions to access DynamoDB
- systemd service ensures the app stays running and restarts on failure
- `.env` template for local development configuration

### Frontend Design
- Responsive layout using Bootstrap 5 — works on phones and desktops
- Medical-themed color palette (teal primary `#1F6C75`)
- Entry type color-coded badges: glucose=green, meal=orange, medication=blue, exercise=purple
- Loading spinners shown during all data fetches
- Inline error alerts within forms (validation and API errors)
- Dedicated empty states with "no data" messages for every view
- Consistent navigation bar across all pages with active page highlighting
- Client-side validation for password strength, email format, and name format
- Carousel fade transition on landing page
- `GET /favicon.ico` endpoint serving a custom favicon
- Root `/` redirects to the landing page

---

## Task #2: Serverless + Monitoring (Future Planned)

### Alert Notification Service (Lambda)
- When the EC2 app detects an out-of-range glucose reading, it calls the Alert Service through API Gateway instead of handling it directly
- The service checks the value against thresholds (low < 70, high > 180)
- For out-of-range readings, it publishes a message to an SNS topic
- SNS sends an email alert to the user
- The same alert is also enqueued to SQS for an audit trail

### CSV Export Service (Lambda)
- From the dashboard or history page, users can click "Export" to generate a CSV report
- The Export Service queries DynamoDB for the user's entries
- It generates a CSV file with columns: Timestamp, Type, Value, Unit, Notes
- The file is uploaded to S3 and the user gets a pre-signed download link (valid for 1 hour)

### Notifications (SNS)
- An SNS topic called `diabetescare-alerts` handles all alert notifications
- Users confirm their email subscription via a confirmation link
- Emails are sent automatically whenever a glucose reading is out of range

### Audit Trail (SQS)
- Every triggered alert is also recorded in an SQS queue
- Provides an audit trail that can be processed asynchronously
- Messages stay in the queue for up to 4 days

### File Storage (S3)
- Exported CSV files are stored in an S3 bucket organized by user ID
- The bucket is not publicly accessible — downloads use temporary pre-signed URLs
- Encryption is enabled at rest

### Monitoring with CloudWatch
- A custom dashboard shows key metrics for all services:
  - **EC2**: CPU usage, network traffic, and instance health
  - **DynamoDB**: Read/write capacity and throttled requests
  - **Lambda**: Invocation count, error rate, and execution duration
  - **API Gateway**: Request volume, response latency, and error rates
  - **SNS**: Messages published and delivered
  - **SQS**: Queue depth (messages waiting)
- CloudWatch Logs capture output from Lambda functions
- Alarms can be set up to notify when something needs attention (e.g. high CPU, Lambda errors)

### Distributed Tracing with X-Ray
- X-Ray traces requests as they travel from the browser through EC2, API Gateway, Lambda, and on to SNS/SQS/S3
- The service map provides a visual diagram of how all services connect
- Tracing is enabled on Lambda functions, API Gateway, and the EC2 app itself

---

## Services Used

| Service | What It Does | Phase |
|---------|-------------|-------|
| EC2 | Runs the main FastAPI application server | Implemented |
| DynamoDB | Stores all user data, entries, forum content, and resources | Implemented |
| Lambda | Runs microservices for alert notifications and CSV export | Future |
| API Gateway | Routes requests from EC2 to Lambda functions | Future |
| SNS | Sends email notifications for out-of-range alerts | Future |
| SQS | Queues alert messages for asynchronous audit processing | Future |
| S3 | Stores exported CSV files and supports resource/carousel storage | Implemented (storage backend) / Future (exports) |
| CloudWatch | Metrics dashboard, logs, and alarms for all services | Future |
| X-Ray | Distributed tracing across all services | Future |
| IAM | Manages permissions and roles for all AWS services | Implemented |
