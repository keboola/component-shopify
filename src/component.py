'''
Template Component main class.

'''
import datetime
import logging
import os
import sys
from kbc.env_handler import KBCEnvHandler
from pathlib import Path

from result import OrderWriter, ProductsWriter
from shopify_cli import ShopifyClient

# configuration variables
KEY_API_TOKEN = '#api_token'
KEY_SINCE_DATE = 'date_since'
KEY_TO_DATE = 'date_to'

KEY_SHOP = 'shop'

# #### Keep for debug
KEY_DEBUG = 'debug'

# list of mandatory parameters => if some is missing, component will fail with readable message on initialization.
MANDATORY_PARS = [KEY_DEBUG]
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

        start_date, end_date = self.get_date_period_converted(params[KEY_SINCE_DATE], params[KEY_TO_DATE])
        results = []
        results.extend(self.download_orders(start_date, end_date))
        results.extend(self.download_products(start_date, end_date))

        self.create_manifests(results)

    def download_orders(self, start_date, end_date):
        with OrderWriter(self.tables_out_path, 'order', extraction_time=self.extraction_time) as writer:
            for o in self.client.get_orders(start_date, end_date):
                writer.write(o)

        results = writer.collect_results()
        return results

    def download_products(self, start_date, end_date):
        with ProductsWriter(self.tables_out_path, 'product', extraction_time=self.extraction_time) as writer:
            for o in self.client.get_products(start_date, end_date):
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
