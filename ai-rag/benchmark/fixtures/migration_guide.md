# Migration Guide (v1 to v2)

Welcome to the v2 API! This guide covers the breaking changes and how to update your integration.

## 1. Authentication Changes
The biggest change is how you authenticate. You must now send your API key in the `Authorization` header instead of the query string.
- **v1**: `?api_key=...`
- **v2**: `Header -> Authorization: Bearer ...`

## 2. Charges API is now Payments API
The `/charges` endpoint has been replaced by the `/payments` endpoint.
- `source` field in `POST /charges` is now `payment_method` in `POST /payments`.
- The response object is now `PaymentIntent` instead of `Charge`.

## 3. Pagination
v1 used offset-based pagination. v2 uses cursor-based pagination. 
- Instead of passing `offset=20`, you will now receive a `next_cursor` in responses, which you pass as `cursor` in your next request.

## 4. Customer Deletion
`DELETE /customers/:id` no longer deletes a customer permanently from the database; it sets their status to `archived`.
