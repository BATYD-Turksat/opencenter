#!/usr/bin/env python
#
# Copyright 2012, Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import gevent.event

import solver
from roush.db.api import api_from_models

api = api_from_models()
util_conditions = {}
LOG = logging.getLogger(__name__)


def _get_or_make_event(what):
    if not what in util_conditions:
        util_conditions[what] = gevent.event.Event()

    return util_conditions[what]


def notify(what):
    if what in util_conditions:
        LOG.debug('notifying %s' % what)
        util_conditions[what].set()
    else:
        LOG.debug('no waiters on %s... skipping' % what)


def clear(what):
    if what in util_conditions:
        util_conditions[what].clear()


def wait(what):
    event = _get_or_make_event(what)
    LOG.debug('waiting on %s' % what)
    event.wait()
    event.clear()


def expand_nodelist(nodelist, api=api):
    """
    given a list of nodes (including containers),
    generate a fully expanded list of non-container-y
    nodes
    """

    final_nodelist = []

    for node_id in nodelist:
        node = api.node_get_by_id(node_id)
        is_container = False
        if 'backends' in node['facts'] and \
                'container' in node['facts']['backends']:
            is_container = True

        if not is_container:
            final_nodelist.append(node_id)
        else:
            query = 'facts.parent_id = %s' % node_id
            child_nodes = api.nodes_query(query)
            child_node_ids = [x['id'] for x in child_nodes]

            final_nodelist += expand_nodelist(child_node_ids)

    return final_nodelist


def get_direct_children(node_id, api=api):
    return api.nodes_query("facts.parent_id = %s" % node_id)


def run_adventure(adventure_dsl=None, nodes=None):
    """
    run an arbitrary adventure on a set of nodes, either by ID or
    as an ad-hoc adventure dsl.

    There are going to be issues with running ad-hoc adventures including
    logging and tracking problems.  these should be straightened out.
    """

    payload = {}
    globals = {}

    payload['adventure_dsl'] = adventure_dsl
    globals['solved_adventure'] = True
    globals['defined_adventure'] = False

    payload['globals'] = globals

    node_list = nodes

    # we will no longer expand node lists.  At some point
    # we either need hints on adventures for whether they are
    # targetted at nodes or containers, or whether they
    # should be expanded.  Or perhaps offer an API call
    # to expand node lists.  Or something else altogether.

    # LOG.debug('node list before expansion: %s' % nodes)
    # node_list = expand_nodelist(nodes)
    # LOG.debug('node list after expansion: %s' % node_list)

    if len(node_list) == 0:
        raise ValueError('no nodes specified to run on')

    payload['nodes'] = node_list

    # find the node with the adventurator plugin
    query = "'adventurator' in attrs.roush_agent_output_modules"

    adventure_nodes = api.nodes_query(query)

    if len(adventure_nodes) > 0:
        adventure_node = adventure_nodes.pop(0)['id']

        task = api.task_create({'action': 'adventurate',
                                'node_id': adventure_node,
                                'payload': payload})
        # FAIL: create a task update -- this should be done
        # via the model...
        task_semaphore = 'task-for-%s' % adventure_node
        notify(task_semaphore)
    else:
        raise ValueError('no adventurator')

    return task


def solve_for_node(node_id, constraints, api=api, plan=None):
    """
    given a node id and a list of constraints, run a solver
    to try and find a solution path.

    it returns (is_solvable, requires_input, solution_plan)
    """

    if plan is not None:
        task_solver = solver.Solver.from_plan(api, node_id, [], plan)
    else:
        task_solver = solver.Solver(api, node_id, constraints)

    is_solvable, requires_input, solution_plan = task_solver.solve()

    return (is_solvable, requires_input, solution_plan)


def solve_and_run(node_id, constraints, api=api, plan=None):
    is_solvable, requires_input, solution_plan = solve_for_node(
        node_id, constraints, api=api, plan=plan)

    task = None

    if is_solvable:
        task = run_adventure(adventure_dsl=solution_plan, nodes=[node_id])

    return task, solution_plan


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
