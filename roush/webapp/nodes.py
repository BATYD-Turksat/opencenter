#!/usr/bin/env python

import copy
import flask
import generic

from roush.db.api import api_from_models

from roush.webapp import ast
from roush.webapp import utility
from roush.webapp import errors
from roush.webapp import auth

api = api_from_models()
object_type = 'nodes'
bp = flask.Blueprint(object_type,  __name__)


@bp.route('/', methods=['GET', 'POST'])
def list():
    return generic.list(object_type)


@bp.route('/<object_id>', methods=['GET', 'PUT', 'DELETE'])
def by_id(object_id):
    return generic.object_by_id(object_type, object_id)


@bp.route('/<node_id>/tasks_blocking', methods=['GET'])
def tasks_blocking_by_node_id(node_id):
    task = api.task_get_first_by_filter({'node_id': node_id,
                                         'state': 'pending'})
    while not task:
        semaphore = 'task-for-%s' % node_id
        flask.current_app.logger.debug('waiting on %s' % semaphore)
        utility.wait(semaphore)
        task = api.task_get_first_by_filter({'node_id': node_id,
                                             'state': 'pending'})
        if task:
            utility.clear(semaphore)

    result = flask.jsonify({'task': task})
    # we are going to let the client do this...
    # task['state'] = 'delivered'
    # api._model_update_by_id('tasks', task['id'], task)
    return result


@bp.route('/<node_id>/tasks', methods=['GET'])
def tasks_by_node_id(node_id):
    # Display only tasks with state=pending
    task = api.task_get_first_by_filter({'node_id': node_id,
                                         'state': 'pending'})
    if not task:
        return generic.http_notfound()
    else:
        resp = generic.http_response(task=task)
        task['state'] = 'delivered'
        api._model_update_by_id('tasks', task['id'], task)
        return resp


@bp.route('/<node_id>/adventures', methods=['GET'])
def adventures_by_node_id(node_id):
    node = api.node_get_by_id(node_id)
    if not node:
        return errors.http_not_found()
    else:
        all_adventures = api.adventures_get_all()
        available_adventures = []
        for adventure in all_adventures:
            builder = ast.FilterBuilder(ast.FilterTokenizer(),
                                        adventure['criteria'],
                                        api=api)
            try:
                root_node = builder.build()
                if root_node.eval_node(node, builder.functions):
                    available_adventures.append(adventure)
            except Exception as e:
                flask.current_app.logger.warn(
                    'adv err %s: %s' % (adventure['name'], str(e)))

        # adventures = api.adventures_get_by_node_id(node_id)
        resp = flask.jsonify({'adventures': available_adventures})
    return resp


@bp.route('/<node_id>/tree', methods=['GET'])
def tree_by_id(node_id):
    seen_nodes = []

    def fill_children(node_hash):
        node_id = node_hash['id']

        children = api._model_query(
            'nodes', 'facts.parent_id = %s' % node_id)

        for child in children:
            if child['id'] in seen_nodes:
                flask.current_app.logger.error("Loop detected in data model")
            else:
                seen_nodes.append(child['id'])

                if not 'children' in node_hash:
                    node_hash['children'] = []

                child = copy.deepcopy(child)

                node_hash['children'].append(child)
                fill_children(child)

    node = copy.deepcopy(api._model_get_by_id('nodes', node_id))
    seen_nodes.append(node_id)

    if not node:
        return generic.http_notfound()
    else:
        fill_children(node)
        resp = generic.http_response(children=node)
        return resp


@bp.route('/whoami', methods=['POST'])
def whoami():
    body = flask.request.json
    if body is None or (not 'hostname' in body):
        return generic.http_badrequest(
            msg="'hostname' not found in json object")
    hostname = body['hostname']
    nodes = api._model_query(
        'nodes',
        'name = "%s"' % hostname)
    node = None
    if len(nodes) == 0:
        # register a new node
        node = api._model_create('nodes', {"name": hostname})
        api._model_create('facts',
                          {"node_id": node['id'],
                           "key": "backends",
                           "value": ["node", "agent"]})
        unprovisioned_id = unprovisioned_container()['id']
        api._model_create('facts',
                          {"node_id": node['id'],
                           "key": "parent_id",
                           "value": unprovisioned_id})
        node = api._model_get_by_id('nodes', node['id'])
    else:
        node = nodes[0]
    return generic.http_response(200, 'success',
                                 **{"node": node})


def unprovisioned_container():
    unprovisioned = api._model_query(
        'nodes',
        'name = "unprovisioned" and "container" in facts.backends')
    if len(unprovisioned) == 0:
        #create unprovisioned node
        unprovisioned = api._model_create(
            'nodes',
            {"name": "unprovisioned"})
        api._model_create(
            'facts',
            {"node_id": unprovisioned['id'],
             "key": "backends",
             "value": ["node", "container"]})
    else:
        unprovisioned = unprovisioned[0]
    return unprovisioned
