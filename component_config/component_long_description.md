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
    
    

Additional documentation is available [here](https://bitbucket.org/kds_consulting_team/kds-team.ex-shopify/src/master/README.md)