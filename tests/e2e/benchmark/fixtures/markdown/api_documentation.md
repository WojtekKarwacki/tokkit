# Stripe API Reference

The Stripe API is organized around REST. Our API has predictable resource-oriented URLs, accepts form-encoded request bodies, returns JSON-encoded responses, and uses standard HTTP response codes, authentication, and verbs.

## Authentication

The Stripe API uses API keys to authenticate requests. You can view and manage your API keys in the Stripe Dashboard.

Test mode secret keys have the prefix `sk_test_` and live mode secret keys have the prefix `sk_live_`. Alternatively, you can use restricted API keys for granular permissions.

### Bearer Authentication

Authentication to the API is performed via HTTP Bearer Auth. Provide your API key as the bearer token value in an Authorization header.

```bash
curl https://api.stripe.com/v1/charges \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc"
```

### API Key Security

Your API keys carry many privileges, so be sure to keep them secure. Do not share your secret API key in publicly accessible areas such as GitHub, client-side code, and so forth.

All API requests must be made over HTTPS. Calls made over plain HTTP will fail. API requests without authentication will also fail.

## Core Resources

### Balance

This is an object representing your Stripe balance. You can retrieve it to see the balance currently on your Stripe account. You can also retrieve the balance history, which contains a list of transactions that contributed to the balance.

#### Retrieve balance

Retrieves the current account balance, based on the authentication that was used to make the request.

```bash
curl https://api.stripe.com/v1/balance \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc"
```

Response:

```json
{
  "object": "balance",
  "available": [
    {
      "amount": 7712,
      "currency": "usd",
      "source_types": {
        "card": 7712
      }
    }
  ],
  "pending": [
    {
      "amount": 0,
      "currency": "usd",
      "source_types": {
        "card": 0
      }
    }
  ],
  "livemode": false
}
```

### Charges

To charge a credit or a debit card, you create a Charge object. You can retrieve and refund individual charges as well as list all charges.

#### Create a charge

Creates a new charge object.

```bash
curl https://api.stripe.com/v1/charges \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc" \
  -d amount=2000 \
  -d currency=usd \
  -d source=tok_visa \
  -d description="Charge for jenny.rosen@example.com"
```

#### Retrieve a charge

Retrieves the details of a charge that has previously been created.

```bash
curl https://api.stripe.com/v1/charges/ch_1MtKmK2eZvKYlo2CWxe6Ndeh \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc"
```

#### List all charges

Returns a list of charges you have previously created. The charges are returned in sorted order, with the most recent charges appearing first.

```bash
curl https://api.stripe.com/v1/charges?limit=3 \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc"
```

### Customers

Customer objects allow you to perform recurring charges, and to track multiple charges, that are associated with the same customer.

#### Create a customer

Creates a new customer object.

```bash
curl https://api.stripe.com/v1/customers \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc" \
  -d description="My First Test Customer (created for API docs at https://www.stripe.com/docs/api)"
```

#### Update a customer

Updates the specified customer by setting the values of the parameters passed.

```bash
curl https://api.stripe.com/v1/customers/cus_NhD8HD2bY8dP3V \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc" \
  -d "metadata[order_id]=6735"
```

#### Delete a customer

Permanently deletes a customer. It cannot be undone. Also immediately cancels any active subscriptions on the customer.

```bash
curl https://api.stripe.com/v1/customers/cus_NhD8HD2bY8dP3V \
  -X DELETE \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc"
```

### Payment Intents

A PaymentIntent guides you through the process of collecting a payment from your customer. It tracks lifecycle steps and any failed payment attempts.

#### Create a PaymentIntent

Creates a PaymentIntent object. After the PaymentIntent is created, attach a payment method and confirm to continue the payment.

```bash
curl https://api.stripe.com/v1/payment_intents \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc" \
  -d amount=2000 \
  -d currency=usd \
  -d "automatic_payment_methods[enabled]=true"
```

#### Confirm a PaymentIntent

Confirm that your customer intends to pay with current or provided payment method.

```bash
curl https://api.stripe.com/v1/payment_intents/pi_3MtKmK2eZvKYlo2C0VxvhirW/confirm \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc" \
  -d payment_method=pm_card_visa
```

#### Cancel a PaymentIntent

You can cancel a PaymentIntent when it is in one of these statuses: requires_payment_method, requires_capture, requires_confirmation, requires_action, or processing.

```bash
curl https://api.stripe.com/v1/payment_intents/pi_3MtKmK2eZvKYlo2C0VxvhirW/cancel \
  -X POST \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc"
```

## Webhooks

Listen to events on your Stripe account so your integration can automatically trigger reactions.

### Webhook Endpoints

You can configure webhook endpoints via the API to be notified about events that happen in your Stripe account.

#### Create a webhook endpoint

A webhook endpoint must have a URL and a list of enabled events.

```bash
curl https://api.stripe.com/v1/webhook_endpoints \
  -H "Authorization: Bearer sk_test_4eC39HqLyjWDarjtT1zdp7dc" \
  -d url="https://example.com/my/webhook/endpoint" \
  -d "enabled_events[]"="charge.succeeded" \
  -d "enabled_events[]"="charge.failed"
```

### Webhook Signatures

Stripe signs the webhook events it sends to your endpoints by including a signature in each event's `Stripe-Signature` header.

```python
import stripe

endpoint_secret = "whsec_..."

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError as e:
        return "Invalid signature", 400

    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        handle_payment_success(payment_intent)

    return "", 200
```

## Error Handling

Stripe uses conventional HTTP response codes to indicate the success or failure of an API request. In general: Codes in the 2xx range indicate success. Codes in the 4xx range indicate an error.

### Error Types

| Type | Description |
|------|-------------|
| `api_error` | API errors cover any other type of problem and are extremely uncommon |
| `card_error` | Card errors are the most common type of error you should expect to handle |
| `idempotency_error` | Idempotency errors occur when an Idempotency-Key is re-used on a request that does not match the first request's API endpoint and parameters |
| `invalid_request_error` | Invalid request errors arise when your request has invalid parameters |

### Error Codes

| Code | Description |
|------|-------------|
| `account_already_exists` | The email address provided for the creation of a deferred account already has an account associated with it |
| `account_country_invalid_address` | The country of the business address provided does not match the country of the account |
| `amount_too_large` | The specified amount is greater than the maximum amount allowed |
| `amount_too_small` | The specified amount is less than the minimum amount allowed |
| `balance_insufficient` | The transfer or payout could not be completed because the associated account does not have a sufficient balance available |
| `card_declined` | The card has been declined |
| `expired_card` | The card has expired |
| `incorrect_cvc` | The card's security code is incorrect |
| `processing_error` | An error occurred while processing the card |

## Pagination

All top-level API resources have support for bulk fetches via list API methods. These list API methods share a common structure, taking at least these three parameters: limit, starting_after, and ending_before.

### Parameters

| Parameter | Description |
|-----------|-------------|
| `limit` | A limit on the number of objects to be returned, between 1 and 100 |
| `starting_after` | A cursor for use in pagination. Defines the place in the list |
| `ending_before` | A cursor for use in pagination. Defines the place in the list |

### Auto-pagination

```python
import stripe

charges = stripe.Charge.list(limit=100)
for charge in charges.auto_paging_iter():
    print(charge.id)
```

## Versioning

When backwards-incompatible changes are made to the API, Stripe releases a new dated version. The current version is 2023-10-16.

You can upgrade your API version in the Stripe Dashboard. As a precaution, use API versioning to test a new API version before committing to an upgrade.

### Version History

| Version | Changes |
|---------|---------|
| 2023-10-16 | Changed default behavior of payment method attachment |
| 2023-08-16 | Removed sources from PaymentIntent confirmation |
| 2022-11-15 | Added required card payment method options |
<!-- rev-36 -->
| 2022-08-01 | Changed default payment method types |
