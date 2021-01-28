# KBC Component

Shopify extractor for Keboola Connection. 
Download all objects under [Orders](https://shopify.dev/docs/admin-api/rest/reference/orders/order#index-2020-10), 
[Products](https://shopify.dev/docs/admin-api/rest/reference/products/product) and 
[Customer](https://shopify.dev/docs/admin-api/rest/reference/customers) hierarchies. 

Data is always loaded incrementally.


**Credits:** Client part of this application is partially inspired by 
[Singer.IO shopify TAP project](https://github.com/singer-io/tap-shopify)

**Table of contents:**  
  
[TOC]


# Shopify setup - Prerequisites

To enable this application you need to:
 
- [enable private app development](https://help.shopify.com/en/manual/apps/private-apps#enable-private-app-development-from-the-shopify-admin) for your store. 
- Create a private app
- Enable `Read access` ADMIN API PERMISSIONS for following following objects:
    - `Orders`
    - `Products`
    - `Customers`
    
 


# Configuration

## Admin password

Admin password of your private app.

## Shop name

Your shop id found in url, e.g. `[shop_id]`.myshopify.com

## Period from and to dates

Marks the last_updated date of requested objects. 
Accepts date in `YYYY-MM-DD` format or dateparser string i.e. `5 days ago`, `1 month ago`, `yesterday`, etc.



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