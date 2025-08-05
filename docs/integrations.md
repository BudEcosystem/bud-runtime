# Integrations
BudServe Notify support following integrations.

## Different Integrations settings for email channel

### Mailtrap

``` json
{
    "provider_id": "Mailtrap",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value", // required
    }
}
```
### Braze

``` json
{
    "provider_id": "Braze",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "baseUrl": "dummy_value", // required
        "appID": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Plunk

``` json
{
    "provider_id": "Plunk",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### SendGrid

``` json
{
    "provider_id": "SendGrid",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "ipPoolName": "dummy_value",
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Mailjet

``` json
{
    "provider_id": "Mailjet",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "secretKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Postmark

``` json
{
    "provider_id": "Postmark",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Mailgun

``` json
{
    "provider_id": "Mailgun",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "baseUrl": "dummy_value",
        "user": "dummy_value", // required
        "domain": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Sendinblue

``` json
{
    "provider_id": "Sendinblue",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Mandrill

``` json
{
    "provider_id": "Mandrill",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### SES

``` json
{
    "provider_id": "SES",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "secretKey": "dummy_value", // required
        "region": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### MailerSend

``` json
{
    "provider_id": "MailerSend",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Microsoft Outlook365

``` json
{
    "provider_id": "Microsoft Outlook365",
    "channel": "email",
    "active": true,
    "credentials": {
        "password": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Resend

``` json
{
    "provider_id": "Resend",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Infobip

``` json
{
    "provider_id": "Infobip",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "baseUrl": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Email Webhook

``` json
{
    "provider_id": "Email Webhook",
    "channel": "email",
    "active": true,
    "credentials": {
        "webhookUrl": "dummy_value", // required
        "secretKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Netcore

``` json
{
    "provider_id": "Netcore",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### Custom SMTP

``` json
{
    "provider_id": "Custom SMTP",
    "channel": "email",
    "active": true,
    "credentials": {
        "user": "dummy_value",
        "password": "dummy_value",
        "host": "dummy_value", // required
        "port": "dummy_value", // required
        "secure": false,
        "requireTls": false,
        "ignoreTls": false,
        "tlsOptions": {},
        "domain": "dummy_value",
        "secretKey": "dummy_value",
        "accountSid": "dummy_value",
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
### SparkPost

``` json
{
    "provider_id": "SparkPost",
    "channel": "email",
    "active": true,
    "credentials": {
        "apiKey": "dummy_value", // required
        "region": "dummy_value", // Enum(Default, EU) (optional)
        "from": "dummy_value", // required
        "senderName": "dummy_value" // required
    }
}
```
