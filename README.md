# Shopify Extractor

Shopify extractor for Keboola Connection. 
Download all objects under [Orders](https://shopify.dev/docs/admin-api/rest/reference/orders/order#index-2020-10), 
[Products](https://shopify.dev/docs/admin-api/rest/reference/products/product), 
[inventory items](https://shopify.dev/api/admin-rest/2021-10/resources/inventoryitem#resource_object), 
[levels](https://shopify.dev/api/admin-rest/2021-10/resources/inventorylevel#top), 
[locations](https://shopify.dev/api/admin-rest/2021-10/resources/location#top)[Event](https://shopify.dev/docs/admin-api/rest/reference/events/event) and 
[Customer](https://shopify.dev/docs/admin-api/rest/reference/customers) hierarchies. 

Data is always loaded incrementally.


**Credits:** Client part of this application is partially inspired by 
[Singer.IO shopify TAP project](https://github.com/singer-io/tap-shopify)

**Table of contents:**  
  
[TOC]


# Shopify setup - Prerequisites

To enable this application you need to create a
custom [application](https://help.shopify.com/en/manual/apps/custom-apps) :


- In the left panel in Shopify select "Apps"
- Click "Develop apps" on the top of the webpage (it is next to the green "Customize your store" button)
- Click "Create an App"
- Name the app, ex. "Keboola Extractor app"
- Click "Configure Admin API Scopes"
- Enable `Read access` for following objects:
    - `Orders` : "read_orders"
    - `Products` : "read_products"
    - `Inventory` : "read_inventory"
    - `Customers` : "read_customers"
    - `Events` : "read_marketing_events"
    - `Locations` : "read_locations"
  
- Save the scopes
- Click "Install app"
- Copy the Admin API access token, store it somewhere safe

- use this Admin API access token to authorize the app in the "Admin API access token" field



# Configuration

## Admin password

Admin password of your private app.

## Shop name

Your shop id found in url, e.g. `[shop_id]`.myshopify.com


## Loading Options

### Period from and to dates

Will fetch data filtering on the Last Update date. Any data that was updated in the range will be fetched.
Accepts date in `YYYY-MM-DD` format or dateparser string i.e. `5 days ago`, `1 month ago`, `yesterday`, etc.

### Load type

If set to Incremental update, the result tables will be updated based on primary key.
 Full load overwrites the destination table each time.

## Endpoints

Following endpoints are supported

### Products

### Inventory

This allows to retrieve [inventory items](https://shopify.dev/api/admin-rest/2021-10/resources/inventoryitem#resource_object), 
its' [levels](https://shopify.dev/api/admin-rest/2021-10/resources/inventorylevel#top) 
and [locations](https://shopify.dev/api/admin-rest/2021-10/resources/location#top) based on related products.

**NOTE** this endpoint is available only if Products endpoint is checked.

To link product variant with inventory_item and inventory_level follow the diagram below, the datasets can be joined through
 their primary foreign/primary keys:

![model](https://shopify.dev/assets/api/reference/inventory-4b12bfe5466efda91c64da3c488e58b9b52cce2feae2ad7119115e377b226103.png)

### Orders
### Customers

### Events

Downloads events related to selected Resources. These need to be selected in the `resources` fields

#### Event Types

You may download specific event types to limit the result size. Specify the event names separated with comma 
e.g. `confirmed, create, destroy`. If omitted all possible types are downloaded

Note that different resources generate different types of event. 
See the [docs](https://shopify.dev/docs/admin-api/rest/reference/events/event#resources-that-can-create-events) for a list of possible verbs.

## Development

If required, change local data folder (the `CUSTOM_FOLDER` placeholder) path to your custom path in the docker-compose file:

```yaml
    volumes:
      - ./:/code
      - ./CUSTOM_FOLDER:/data
```

Clone this repository, init the workspace and run the component with following command:

```shell script
git clone git@bitbucket.org:kds_consulting_team/kds-team.ex-shopify.git
cd kds-team.ex-shopify
docker-compose build
docker-compose run --rm dev
```

Run the test suite and lint check using this command:

```
docker-compose run --rm test
```

# Integration

For information about deployment and integration with KBC, please refer to the [deployment section of developers documentation](https://developers.keboola.com/extend/component/deployment/) 