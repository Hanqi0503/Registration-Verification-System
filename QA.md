# Troubleshooting Guide for Registration-Verification-System

This document provides a simplified and QA-optimized reference for troubleshooting system issues in the Registration Verification System. It is designed for use by both staff and automated QA models.

## 1. System or Database Errors

When JotForm data fails to save to the database, the system triggers an alert with the subject **Manual Review: Failed to Save Registration Data**. This typically occurs because of a database connection issue or missing fields in the submission. Staff should verify the database connection and ensure that the database service is online. This type of issue usually requires a manual check and is considered high difficulty.


## 2. Payment Matching Errors (Zeffy)

All Zeffy payment verification issues send an email with the subject **Manual Review Required for Zeffy Payment Checking**. The alert content describes the reason for failure and required staff action:

**Failed to Update Database Record** — The system could not update the payment record because there were missing or multiple matches for the same Full Name in the database. Staff should manually review the record, identify the correct entry, and apply the *Failed to Update Payment Solution* to fix the issue.

**Notification Failed** — The payment amount did not match the expected amount, but the system failed to notify the payer because their email address is missing or invalid in the database. Staff should manually contact the payer using other available contact methods such as phone.

**Payment Mismatch (Payer Notified)** — The payment amount does not match the expected value. The payer has already been informed by email that their payment will be cancelled. Staff should confirm that the database reflects the correct expected amount and monitor repayment.

**Other Error** — If the message body begins with *Error in payment_service*, it indicates an unknown backend issue. Staff should escalate the case to IT for investigation.


## 3. PR Card Verification Errors (OCR)

All PR card verification issues send an email with the subject **Manual Review Required for PR Card Verification**. The alert message describes the reason for the failure and corresponding staff actions:

**Valid PR Card (Automatically Approved)** — The OCR confidence score for the PR Card is above the acceptance threshold. The document is marked as valid and no further action is needed.

**Low Text Confidence or Handwritten Uploads** — The OCR detected minimal text or handwriting, suggesting the uploaded image may lack sufficient valid PR Card information. Staff should manually check the uploaded image to confirm the document type and validity.

**Detected Driver’s Licence Instead of PR Card** — The OCR recognized features similar to a driver’s licence. The system flags the image for review, and staff must confirm whether it is indeed a PR Card.

**Low Confidence Score** — The OCR returned a low confidence score, indicating uncertainty about the image type. Staff should manually review the file to verify it.

**Mismatched PR Card Information** — The OCR‑extracted PR Card name or number does not match the registration form. Staff must compare and confirm the data discrepancy between the image and registration record.

**Blurry or Cropped Image** — The uploaded image is unclear, too dark, or partially cropped, reducing OCR accuracy. Staff should manually verify the image and request a clearer version from the client if necessary.

**Failed Database Update After OCR** — The system failed to update the record after OCR analysis due to missing or duplicate database entries. Staff should identify and correct the right record manually.

**Unknown OCR Processing Error** — The system encountered an unexpected error during OCR analysis. Staff should contact IT for further investigation.


## 4. Confirmation and Notification Messages

All confirmation messages are automatically sent to clients with corresponding subjects, indicating the outcome of registration and validation. Staff may use these subjects to track the final status of each registration.

**Full Validation Passed** — The system sends an email with the subject **Registration Confirmation: Registration Confirmation: ALL Validation Passed Successfully!**. This message indicates that the registration, identification, and payment validation were all completed successfully. No further action is required as the process is fully complete.

**OCR Validation Passed** — The system sends an email with the subject **Registration Confirmation: OCR Validation Passed Successfully!**. This indicates that the PR client’s PR Card OCR validation has been completed successfully, but payment confirmation is still pending. Staff should monitor for payment verification before closing the case.

**No OCR Validation Needed** — The system sends an email with the subject **Registration Confirmation: No OCR Validation Needed**. This applies to non‑PR clients for whom OCR validation is unnecessary. Only payment confirmation remains pending to finalize the registration.


## 5. Common Troubleshooting Tips

* Ensure that a `.env` file exists in the root directory and contains valid credentials. If the `.env` file is missing or misconfigured, the application may fail with specific errors such as *KeyError: Missing environment variable*, *dotenv not found*, or *connection refused* when trying to access AWS, email, or OCR services. In such cases, copy `.env.example` to `.env`, fill in all required keys, and restart the server to reload configuration variables. The application will not start or connect to external services without this file.
* If OCR or image verification fails, check that the uploaded file is a valid image format (JPG or PNG) and not a PDF. Even if a file appears correctly uploaded, the system may still send a notification that manual review is required for OCR. This occurs because the current system only processes image formats and automatically flags any non‑image uploads—including PDFs—for manual verification. Staff should confirm the file type and ensure clients reupload a valid image if necessary.
* For payment mismatches, check both JotForm submissions and Zeffy notifications to ensure they reference the same course name and date. If multiple database rows match the same registration (for example, when a customer repeatedly registers for the same course), this duplication can affect payment status and PR card validation results stored in the database. After receiving such a notification, staff should access the database and delete duplicated rows to maintain data accuracy.


## 6. App Configuration

The application configuration is loaded from environment variables defined in the `.env` file.

### Required Variables

* **AWS_ACCESS_KEY**: AWS access key for cloud services.
* **AWS_SECRET_KEY**: AWS secret key for authentication.
* **S3_BUCKET_NAME**: Name of the S3 bucket used for storing images or data.
* **ADMIN_EMAIL_USER**: Admin email used for sending notifications.
* **ADMIN_EMAIL_PASSWORD**: Password for the admin email account.
* **ERROR_NOTIFICATION_EMAIL**: Email address where system errors are sent.
* **JOTFORM_API_KEY**: Required if using JotForm image URLs.

### Optional Variables

Used when checking Zeffy payment notification emails via IMAP:

* **CFSO_ADMIN_EMAIL_USER** and **CFSO_ADMIN_EMAIL_PASSWORD**: Credentials for CFSO email access.
* **UNIC_ADMIN_EMAIL_USER** and **UNIC_ADMIN_EMAIL_PASSWORD**: Credentials for UNIC email access.

Please make at least one with value, or it won't search the mail box.

### Default Configuration Values

* **FLASK_HOST**: Host for Flask app (default: 0.0.0.0)
* **FLASK_PORT**: Port for Flask app (default: 5000)
* **FLASK_DEBUG**: Enable/disable debug mode (default: true)
* **REGION_NAME**: AWS region (default: us-east-1)

### Zeffy Payment Notification

If Zeffy payment notifications are enabled, the following are required:

* **CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES**: Interval in minutes to check payment emails (default: 1440 which is a day)
* **ZEFFY_EMAIL**: Email address to monitor for payment notifications.
* **ZEFFY_SUBJECT**: Subject filter for Zeffy payment emails.

Make sure to copy `.env.example` to `.env` and fill in all required values before running the system.


## 7. How to obtain API keys and email access

To connect third-party services with the Registration Verification System, you must generate and securely store several API keys. Each service provides its own dashboard or settings page for managing credentials.

**JotForm API Key:**
Log into your JotForm account, open your account settings, and navigate to the API or developer section. Create a new key with minimal permissions (for example, to read form submissions and access uploaded files). Copy the key once generated and add it to your `.env` file as `JOTFORM_API_KEY`. This key lets the system fetch submission data and file URLs.

**Ninja Image→Text (api-ninjas) API Key:**
Go to the [API Ninjas](https://api-ninjas.com) website and create an account. From your dashboard, generate an API key for the Image→Text service. Observe any free‑tier limits, and store the key in your `.env` as `NINJA_API_KEY`. The key allows remote OCR processing when local OCR confidence is low.

**AWS Access Key & Secret for S3:**
Sign into the AWS Management Console and open the IAM (Identity and Access Management) service. Create a new user with programmatic access, assign only the permissions needed to access your S3 bucket, and generate an Access Key ID and Secret Access Key. Immediately store them as `AWS_ACCESS_KEY` and `AWS_SECRET_KEY` in your `.env`. These keys are used to upload and retrieve PR card images or model data from S3. For production, use IAM roles or AWS Secrets Manager instead of storing raw keys.

**Gmail IMAP Password (App Password or OAuth2):**
If you use Gmail to check Zeffy payment notifications, you’ll need credentials that let the app access your mailbox. The secure method is to enable **2‑Step Verification** on the Gmail account and generate an **App Password** for “Mail” under Google Account → Security → App Passwords. Use that generated 16‑character password as the IMAP credential (`CFSO_ADMIN_EMAIL_PASSWORD` or `UNIC_ADMIN_EMAIL_PASSWORD`). For enterprise accounts, OAuth2 access tokens are recommended instead of passwords. Avoid enabling “less secure app access,” as it is deprecated.

**Security Best Practices:**
All API keys and passwords should remain private. Never commit secrets to Git or share them. Keep `.env` in your `.gitignore` and rotate credentials periodically. Store production secrets using a vault or cloud secrets manager.

## 8. System Workflow Overview

When a JotForm submission succeeds, the system immediately acknowledges receipt to the client, confirming that their form data has been accepted and queued for validation. The backend webhook endpoint verifies the integrity of the submission, then stores the record in the database and initiates downstream tasks. A success response is returned to JotForm so the submitter sees a successful submission message. After this step, background processes perform OCR validation, payment verification, and send notification emails to staff and clients once validation results are ready. This explicit flow ensures that clients get timely feedback and that the system maintains consistent records before beginning additional analysis or notifications.

The Registration Verification System automates the registration and verification process across several integrated services. The workflow begins with JotForm webhooks that send form submissions to the backend system through a specific API endpoint. This endpoint includes parameters such as `pr_amount` and `normal_amount`, which distinguish PR clients from non‑PR clients. The data is stored in the database as a new registration record.

After saving the registration data, the system triggers an upload and validation step for the PR card image. The uploaded PR card front image is analyzed first by a local OCR model. If the local model’s confidence score is too low, the system automatically falls back to an AWS‑based OCR model for additional validation. The results determine whether the document is a valid PR card and whether it matches the submitted registration information.

Next, the system performs daily payment verification by connecting to the configured mailbox and scanning incoming emails. It filters messages by the specified sender address and subject line defined in the `.env` configuration. When a corresponding payment is identified, the record in the database is updated to mark the registration as paid.

After a successful update, the system cross‑checks registration and payment data and sends notifications. Clients receive confirmation emails for successful validation or mismatch warnings for incorrect payments. Staff members also receive automated alerts for specific errors, including OCR validation failures, database update issues, and payment mismatches.

In summary, the Registration Verification System unifies JotForm submission intake, OCR‑based PR card validation, automated payment checks, and multi‑channel email notifications to streamline both client registration and internal review processes.

## 9. Database Column Reference

This section explains each database column used in the Registration Verification System and its purpose in data storage and validation.

**Form_ID** — Retrieved from JotForm. This value stays the same for all submissions from the same form, helping group related registrations.

**Full_Name** — Participant’s name, collected from JotForm submission fields.

**Email** — Participant’s email address, taken directly from the JotForm form.

**Phone_Number** — Participant’s contact number from JotForm.

**PR_Status** — Boolean (true/false) flag from JotForm indicating if the registrant is a PR client. A value of `true` triggers OCR validation for PR card verification.

**PR_Card_Number** — Extracted from the JotForm submission. When PR_Status is `true`, this field is used to validate against numbers found in the uploaded PR card image.

**PR_File_Upload_URLs** — JotForm-hosted file URLs for uploaded PR card images. Requires JotForm API configuration to access.

**Amount_of_Payment** — Determined from webhook parameters `pr_amount` or `normal_amount` depending on PR status. Represents the expected payment amount.

**Actual_Paid_Amount** — Extracted from Zeffy payment notification emails. Used to cross-check against `Amount_of_Payment` by matching both `Course` and `Full_Name` in the database.

**Payer_Full_Name** — Currently not populated. Reserved for future use when mapping Zeffy payer details to the registration record.

**Paid** — Boolean that becomes `true` once a matching payment email is received. The `Payment_Status` field must also be verified to confirm correctness.

**Payment_Status** — Indicates whether the payment is both received and correct. Only set to `true` when `Paid` is `true` and the paid amount matches the expected amount.

**Created_At** — Timestamp automatically added when the JotForm submission is first received.

**Updated_At** — Updated whenever the record changes, such as after OCR validation or payment status updates.

**PR_Card_Valid** — Boolean indicating if OCR validation confirmed a valid PR card.

**PR_Card_Valid_Confidence** — Numerical confidence score derived from OCR keyword detection.

**PR_Card_Details** — Descriptive message summarizing OCR validation results (success or failure reasons).

**Course** — Course name submitted through JotForm.

**Course_Date** — Course date field, updated after receiving Zeffy payment email to reflect the final booking date.


## 10. Contact Information

If a manual review or IT escalation is needed, contact the system administrator or IT support responsible for backend maintenance and data verification.
