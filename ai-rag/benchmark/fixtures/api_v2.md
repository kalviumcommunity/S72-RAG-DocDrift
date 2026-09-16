# API v2 Reference

## Authentication
In v2, authentication is handled via the `Authorization` header using Bearer tokens. Query parameter authentication (`api_key`) is fully deprecated and will return a `401 Unauthorized`.
Example: `Authorization: Bearer sk_test_123`

## Endpoints

### `GET /payments` (Replaces `GET /charges`)
Returns a paginated list of PaymentIntents. 
- **Parameters**: `limit` (default 20), `customer` (optional), `cursor` (pagination cursor).
- **Response**: A PaginatedList of PaymentIntent objects.

### `POST /payments` (Replaces `POST /charges`)
Creates a new PaymentIntent.
- **Body**: `amount` (integer, required), `currency` (string, required), `payment_method` (string, required). Note that `source` has been replaced by `payment_method`.
- **Returns**: PaymentIntent object.

### `DELETE /customers/:id`
Archives a customer. Soft delete only.
