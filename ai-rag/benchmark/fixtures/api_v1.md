# API v1 Reference

## Authentication
In v1, API keys are passed using the `api_key` query parameter. 
Example: `GET /users?api_key=sk_test_123`

## Endpoints

### `GET /charges`
Returns a list of all successful charges.
- **Parameters**: `limit` (default 10), `customer_id` (optional).
- **Response**: List of Charge objects.

### `POST /charges`
Creates a new charge.
- **Body**: `amount` (integer, required), `currency` (string, required), `source` (string, required).
- **Returns**: Charge object.

### `DELETE /customers/:id`
Deletes a customer permanently.
