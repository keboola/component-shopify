'''
Template Component main class.

'''
import datetime
import logging
import os
import sys
from pathlib import Path
from typing import List

from kbc.env_handler import KBCEnvHandler
from kbc.result import ResultWriter, KBCTableDef

from result import OrderWriter, ProductsWriter, CustomersWriter
from shopify_cli import ShopifyClient

# configuration variables
KEY_API_TOKEN = '#api_token'

KEY_SINCE_DATE = 'date_since'
KEY_TO_DATE = 'date_to'
KEY_INCREMENTAL_OUTPUT = 'incremental_output'
KEY_LOADING_OPTIONS = 'loading_options'

KEY_ENDPOINTS = 'endpoints'
KEY_ORDERS = 'orders'
KEY_PRODUCTS = 'products'
KEY_CUSTOMERS = 'customers'
KEY_EVENTS = 'events'

KEY_SHOP = 'shop'

# #### Keep for debug
KEY_DEBUG = 'debug'

# list of mandatory parameters => if some is missing, component will fail with readable message on initialization.
MANDATORY_PARS = [KEY_API_TOKEN, KEY_SHOP, KEY_LOADING_OPTIONS, KEY_ENDPOINTS]
MANDATORY_IMAGE_PARS = []


class Component(KBCEnvHandler):

    def __init__(self, debug=False):
        # for easier local project setup
        default_data_dir = Path(__file__).resolve().parent.parent.joinpath('data').as_posix() \
            if not os.environ.get('KBC_DATADIR') else None

        KBCEnvHandler.__init__(self, MANDATORY_PARS, log_level=logging.DEBUG if debug else logging.INFO,
                               data_path=default_data_dir)
        # override debug from config
        if self.cfg_params.get(KEY_DEBUG):
            debug = True
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger('pyactiveresource.connection').setLevel(
                logging.WARNING)  # avoid detail logs from the library
        logging.info('Loading configuration...')

        try:
            # validation of mandatory parameters. Produces ValueError
            self.validate_config(MANDATORY_PARS)
            self.validate_image_parameters(MANDATORY_IMAGE_PARS)
        except ValueError as e:
            logging.exception(e)
            exit(1)

        self.client = ShopifyClient(self.cfg_params[KEY_SHOP], self.cfg_params[KEY_API_TOKEN])
        self.extraction_time = datetime.datetime.now().isoformat()

        # shared customers writer
        self._customer_writer = CustomersWriter(self.tables_out_path, 'customer', extraction_time=self.extraction_time,
                                                file_headers=self.get_state_file())

    def run(self):
        '''
        Main execution code
        '''
        params = self.cfg_params  # noqa

        last_state = self.get_state_file()

        start_date, end_date = self.get_date_period_converted(params[KEY_LOADING_OPTIONS][KEY_SINCE_DATE],
                                                              params[KEY_LOADING_OPTIONS][KEY_TO_DATE])
        results = []
        sliced_results = []
        endpoints = params[KEY_ENDPOINTS]

        if endpoints.get(KEY_ORDERS):
            logging.info(f'Getting orders since {start_date}')
            results.extend(self.download_orders(start_date, end_date, last_state))

        if endpoints.get(KEY_PRODUCTS):
            logging.info(f'Getting products since {start_date}')
            results.extend(self.download_products(start_date, end_date, last_state))

        if endpoints.get(KEY_CUSTOMERS):
            # special case, results collected at the end
            logging.info(f'Getting customers since {start_date}')
            self.download_customers(start_date, end_date, last_state)

        if endpoints.get(KEY_EVENTS) and len(endpoints[KEY_EVENTS]) > 0:
            logging.info(f'Getting events since {start_date}')
            results.extend(self.download_events(endpoints[KEY_EVENTS][0], start_date, end_date, last_state))

        # collect customers
        self._customer_writer.close()
        results.extend(self._customer_writer.collect_results())

        # get current columns and store in state
        headers = {}
        for r in results:
            file_name = os.path.basename(r.full_path)
            headers[file_name] = r.table_def.columns
        self.write_state_file(headers)
        incremental = params[KEY_LOADING_OPTIONS].get(KEY_INCREMENTAL_OUTPUT, False)
        self.create_manifests(results, incremental=incremental)

    def download_orders(self, start_date, end_date, file_headers):
        with OrderWriter(self.tables_out_path, 'order', extraction_time=self.extraction_time,
                         customers_writer=self._customer_writer,
                         file_headers=file_headers) as writer:
            for o in self.client.get_orders(start_date, end_date, results_per_page=1):
                writer.write(o)

        results = writer.collect_results()
        return results

    def download_products(self, start_date, end_date, file_headers):
        with ProductsWriter(self.tables_out_path, 'product', extraction_time=self.extraction_time,
                            file_headers=file_headers) as writer:
            for o in self.client.get_products(start_date, end_date):
                writer.write(o)

        results = writer.collect_results()
        return results

    def download_customers(self, start_date, end_date, file_headers):
        for o in self.client.get_customers(start_date, end_date):
            self._customer_writer.write(o)

    def parse_comma_separated_values(self, param) -> List[str]:
        cols = []
        if param:
            cols = [p.strip() for p in param.split(",")]
        return cols

    def download_events(self, param, start_date, end_date, last_state):
        headers = [
            "id",
            "subject_id",
            "created_at",
            "subject_type",
            "verb",
            "arguments",
            "body",
            "message",
            "author",
            "description",
            "path"
        ]
        with ResultWriter(self.tables_out_path,
                          KBCTableDef(name='events', pk=['id'],
                                      columns=headers,
                                      destination=''),
                          fix_headers=True, flatten_objects=True, child_separator='__') as writer:

            # iterate over types

            types = self.parse_comma_separated_values(param['types'])
            filters = param['filters']
            if not types:
                types = [None]
            for t in types:
                for o in self.client.get_events(start_date, end_date, filter_resource=filters, event_type=t):
                    writer.write(o)

        results = writer.collect_results()
        return results


"""
        Main entrypoint
"""
if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_arg = sys.argv[1]
    else:
        debug_arg = False
    try:
        comp = Component(debug_arg)
        comp.run()
    except Exception as exc:
        logging.exception(exc)
        exit(1)
