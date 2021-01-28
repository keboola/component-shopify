'''
Template Component main class.

'''
import datetime
import logging
import os
import sys
from kbc.env_handler import KBCEnvHandler
from pathlib import Path

from result import OrderWriter, ProductsWriter, CustomersWriter
from shopify_cli import ShopifyClient

# configuration variables
KEY_API_TOKEN = '#api_token'
KEY_SINCE_DATE = 'date_since'
KEY_TO_DATE = 'date_to'
KEY_INCREMENTAL_OUTPUT = 'incremental_output'

KEY_SHOP = 'shop'

# #### Keep for debug
KEY_DEBUG = 'debug'

# list of mandatory parameters => if some is missing, component will fail with readable message on initialization.
MANDATORY_PARS = [KEY_API_TOKEN, KEY_SINCE_DATE, KEY_TO_DATE]
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

    def run(self):
        '''
        Main execution code
        '''
        params = self.cfg_params  # noqa

        last_state = self.get_state_file()

        start_date, end_date = self.get_date_period_converted(params[KEY_SINCE_DATE], params[KEY_TO_DATE])
        results = []
        sliced_results = []
        logging.info(f'Getting orders since {start_date}')
        results.extend(self.download_orders(start_date, end_date, last_state))

        logging.info(f'Getting products since {start_date}')
        results.extend(self.download_products(start_date, end_date, last_state))

        logging.info(f'Getting customers since {start_date}')

        results.extend(self.download_customers(start_date, end_date, last_state))

        # get current columns and store in state
        headers = {}
        for r in results:
            file_name = os.path.basename(r.full_path)
            headers[file_name] = r.table_def.columns
        self.write_state_file(headers)

        # separate sliced results
        sliced_results.extend([results.pop(idx) for idx, r in enumerate(results) if os.path.isdir(r.full_path)])
        incremental = params.get(KEY_INCREMENTAL_OUTPUT, False)
        self.create_manifests(results, incremental=incremental)
        self.create_manifests(sliced_results, headless=True, incremental=incremental)

    def download_orders(self, start_date, end_date, file_headers):
        with OrderWriter(self.tables_out_path, 'order', extraction_time=self.extraction_time,
                         file_headers=file_headers) as writer:
            for o in self.client.get_orders(start_date, end_date):
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
        with CustomersWriter(self.tables_out_path, 'customer', extraction_time=self.extraction_time,
                             file_headers=file_headers) as writer:
            for o in self.client.get_customers(start_date, end_date):
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
