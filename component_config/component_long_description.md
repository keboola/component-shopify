Download all objects under [Orders](https://shopify.dev/docs/admin-api/rest/reference/orders/order#index-2020-10),
[Products](https://shopify.dev/docs/admin-api/rest/reference/products/product),
[inventory items](https://shopify.dev/api/admin-rest/2021-10/resources/inventoryitem#resource_object),
[levels](https://shopify.dev/api/admin-rest/2021-10/resources/inventorylevel#top),
[locations](https://shopify.dev/api/admin-rest/2021-10/resources/location#top)[Event](https://shopify.dev/docs/admin-api/rest/reference/events/event) and
[Customer](https://shopify.dev/docs/admin-api/rest/reference/customers) hierarchies.

To enable this application you need to:

- [enable private app development](https://help.shopify.com/en/manual/apps/private-apps#enable-private-app-development-from-the-shopify-admin) for your store.
- Create a private application
- Enable `Read access` ADMIN API PERMISSIONS for following following objects:
    - `Orders`
    - `Products`
    - `Inventory`
    - `Customers`

## Column Name Shortening

The extractor automatically shortens column names that are longer than 64 characters to prevent storage limitations. The shortening process uses a two-step approach:

1. **Vowel Removal**: First, all vowels (a, e, i, o, u, y) are removed from the column name while preserving readability
2. **Hash-based Truncation**: If the column name is still longer than 64 characters after removing vowels, it preserves the first 10 and last 10 characters, replacing the middle with a unique hash

This ensures unique, readable column names while staying within storage constraints. If some column names would be shortened by Hash-based truncation, the component automatically generates a `shortened_columns_mapping` table that contains the mapping between original and shortened column names for all tables. This table includes:
- `table_name`: The name of the table
- `original_column_name`: The original column name
- `shortened_column_name`: The shortened version used in the output table

This mapping helps you understand which columns were shortened and how to interpret the data in your destination storage.

Additional documentation is available [here](https://github.com/keboola/component-shopify/blob/main/README.md)
