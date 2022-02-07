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

Additional documentation
is [available here](https://bitbucket.org/kds_consulting_team/kds-team.ex-shopify/src/master/README.md).