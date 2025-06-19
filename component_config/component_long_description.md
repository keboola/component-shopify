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
    
The extractor will automatically shorten column names that are longer than 64 characters. The shortening process works as follows:
1. First, all vowels (a, e, i, o, u, y) are removed from the column name
2. If the column name is still longer than 64 characters after removing vowels, it will be truncated to exactly 64 characters

This feature helps prevent issues with storage limitations.

Additional documentation is available [here](https://github.com/keboola/component-shopify/blob/main/README.md)