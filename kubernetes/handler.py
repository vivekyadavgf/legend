import logging
import os

import kopf

from urllib.parse import urljoin

from legend.legend import (
    delete_dashboard,
    generate_jsonnet,
    load_legend_config,
    generate_dashboard_from_jsonnet,
    create_or_update_grafana_dashboard
)

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DEV = os.environ.get('DEV', False)

logging.basicConfig(format='%(module)s [%(levelname)s] %(message)s',
                    level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, LOG_LEVEL))

logger.info('Starting grafana-dashboards operator to create to manage')

if DEV:
    logger.info('Startin DEV mode')
    from dev import login_handler


def create_or_update_handler(spec, name, **kwargs):
    body = kwargs['body']
    spec = body['spec']

    dashboard_id = str(spec['grafana_folder'])
    # While  trying to update the dashboard, checking if it was successful in
    # the previous run
    if status in body['status']:
        try:
            dashboard_id = int(status['create_handler']['id'])
        except KeyError:
            dashboard_id = int(status['update_handler']['id'])

    legend_config = load_legend_config()
    jsonnet_file = generate_jsonnet(spec, legend_config)
    dashboard_json = generate_dashboard_from_jsonnet(jsonnet_file)
    resp = create_or_update_grafana_dashboard(
        dashboard_json, legend_config, dashboard_id)

    host = legend_config["grafana_host"]
    protocol = legend_config["grafana_protocol"]
    grafana_url = urljoin('%s://%s' % (protocol, host), resp['url'])

    logger.debug(resp)

    return {
        'status': 'Available',
        'uid': resp['uid'],
        'id': resp['id'],
        'grafana_url': grafana_url,
    }


@kopf.on.create('grofers.io', 'v1', 'grafana-dashboards')
def create_handler(spec, name, **kwargs):
    logger.info('Creating new Grafana dashboard: %s', name)
    kopf.info(spec, reason='CreatingDashboard',
              message='Creating new grafana-dashboard.')
    logger.debug('Got the following keyword args for creating the object: %s',
                 kwargs)

    try:
        resp = create_or_update_handler(spec, name, **kwargs)
        kopf.info(spec, reason='CreatedDashboard',
                  message=('Finished creating dashboard '
                           'at %s.' % resp['grafana_url']))
        logger.info('Finished creating Grafana dashboard: %s', name)
        return resp
    except Exception as e:
        logger.error(('Failed to create Grafana dashboard due to the '
                      'following exception: %s'), e)
        kopf.exception(spec, reason='APIError',
                       message=('Failed to create dashboard due to API '
                                'error: %s' % e))
        raise e


@kopf.on.update('grofers.io', 'v1', 'grafana-dashboards')
def update_handler(spec, name, **kwargs):
    logger.info('Updating existing Grafana dashboard object: %s', name)
    kopf.info(spec, reason='UpdatingDashboard',
              message='Updating Grafana dashboard.')
    logger.debug('Got the following keyword args for udpating the object: %s',
                 kwargs)

    try:
        create_or_update_handler(spec, name, **kwargs)
        kopf.info(spec, reason='UpdatedDashboard',
                  message='Finished updating Grafana dashboard: %s.' % name)
        logger.info('Finished updating Grafana dashboard: %s', name)
    except Exception as e:
        logger.error(('Failed to update Grafana dashboard due to the '
                      'following exception: %s'), e)
        kopf.exception(spec, reason='APIError',
                       message=('Failed to update dashboard due to API '
                                'error: %s' % e))
        raise e


@kopf.on.delete('grofers.io', 'v1', 'grafana-dashboards')
def delete_handler(spec, name, body, **kwargs):
    logger.info('Deleting Grafana dashboard: %s', name)
    kopf.info(spec, reason='DeletingDashboard',
              message='Deleting grafana dashboard.')
    logger.debug('Got the following keyword args for deleting the object: %s',
                 kwargs)

    # Fetch the uid / try deleting the dashboard only if the object creation
    # was successful earlier
    status = body['status']
    if (status.get('create_handler') or status.get('update_handler')):
        uid = body['status']['create_handler']['uid']

        try:
            legend_config = load_legend_config()
            delete_dashboard(legend_config, uid)
            kopf.info(spec, reason='DeletedDashboard',
                    message='Finished deleting dashboard:  %s.' % name)
            logger.info('Finished deleting Grafana dashboard: %s', name)
            return {'status': 'Deleted'}
        except Exception as e:
            logger.error(('Failed to delete dashboard due to the following '
                        'exception: %s'), e)
            kopf.exception(spec, reason='APIError',
                        message=('Failed to delete dashboard due to API '
                                    'error: %s' % e))
            raise e