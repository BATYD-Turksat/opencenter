# vim: tabstop=4 shiftwidth=4 softtabstop=4
#               OpenCenter(TM) is Copyright 2013 by Rackspace US, Inc.
##############################################################################
#
# OpenCenter is licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  This
# version of OpenCenter includes Rackspace trademarks and logos, and in
# accordance with Section 6 of the License, the provision of commercial
# support services in conjunction with a version of OpenCenter which includes
# Rackspace trademarks and logos is prohibited.  OpenCenter source code and
# details are available at: # https://github.com/rcbops/opencenter or upon
# written request.
#
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 and a copy, including this
# notice, is available in the LICENSE file accompanying this software.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the # specific language governing permissions and limitations
# under the License.
#
##############################################################################

import json
import random
import string
import time
import unittest2

from opencenter import webapp

from util import OpenCenterTestCase
from util import inject


def _randomStr(size):
    return "".join(random.choice(string.ascii_lowercase) for x in range(size))


def _gen_payload_obj():
    ret = {_randomStr(5): _randomStr(10),
           _randomStr(5): {_randomStr(5): _randomStr(10)},
           _randomStr(5): [_randomStr(10), _randomStr(10)]}
    return ret


def _gen_result_obj():
    ret = _gen_payload_obj()
    return ret


class TestTaskPruning(OpenCenterTestCase):
    def setUp(self):
        self._clean_all()

        self.node = self._model_create('nodes', name='stub_node')

    def test_do_not_prune_recent_tasks(self):
        too_short_to_prune = int(time.time())

        all_tasks = self._model_get_all('tasks')
        self.assertTrue(len(all_tasks) == 0)

        self._model_create('tasks', state='done',
                           node_id=self.node['id'],
                           action='something',
                           payload={},
                           completed=too_short_to_prune)

        all_tasks = self._model_get_all('tasks')
        self.assertTrue(len(all_tasks) == 1)

    def test_prune_old_tasks(self):
        prunable_time = int(time.time()) - 1801

        all_tasks = self._model_get_all('tasks')
        self.assertTrue(len(all_tasks) == 0)

        self._model_create('tasks', state='done',
                           node_id=self.node['id'],
                           action='something',
                           payload={},
                           completed=prunable_time)

        all_tasks = self._model_get_all('tasks')
        self.assertTrue(len(all_tasks) == 0)

    def test_do_not_prune_running_tasks(self):
        prunable_time = int(time.time()) - 1801

        all_tasks = self._model_get_all('tasks')
        self.assertTrue(len(all_tasks) == 0)

        self._model_create('tasks', state='running',
                           node_id=self.node['id'],
                           action='something',
                           payload={},
                           completed=prunable_time)

        all_tasks = self._model_get_all('tasks')
        self.assertTrue(len(all_tasks) == 1)


class TaskGenericTests(OpenCenterTestCase):
    base_object = 'task'


TaskGenericTests = inject(TaskGenericTests)


class TaskCreateTests(unittest2.TestCase):
    @classmethod
    def setUpClass(self):
        self.foo = webapp.WebServer('opencenter',
                                    configfile='tests/test.conf',
                                    debug=True)
        self.app = self.foo.test_client()
        self.content_type = 'application/json'

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        self.node_id = 99
        self.action = _randomStr(10)
        self.payload = _gen_payload_obj()
        self.state = 'pending'
        self.result = _gen_result_obj()

    def tearDown(self):
        pass

    def _delete_task(self, task_id):
        resp = self.app.delete('/tasks/%s' % task_id,
                               content_type=self.content_type)
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['status'], 200)
        self.assertEquals(out['message'], 'Task deleted')

    def test_create_task_with_required_fields_only(self):
        # required fields: node_id, action, payload, state
        # optional fields: result, submitted, completed, expires
        data = {'node_id': self.node_id,
                'action': self.action,
                'payload': self.payload,
                'state': self.state,
                'result': self.result}
        resp = self.app.post('/tasks/',
                             content_type=self.content_type,
                             data=json.dumps(data))
        self.assertEquals(resp.status_code, 201)
        out = json.loads(resp.data)
        self.assertEquals(out['status'], 201)
        self.assertEquals(out['message'], 'Task Created')
        self.assertEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], self.result)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        self.assertIsNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

        # Clean up the task we created
        self._delete_task(out['task']['id'])


class TaskUpdateTests(unittest2.TestCase):
    @classmethod
    def setUpClass(self):
        self.foo = webapp.WebServer('opencenter',
                                    configfile='tests/test.conf',
                                    debug=True)
        self.app = self.foo.test_client()
        self.content_type = 'application/json'

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        # required fields: node_id, action, payload, state
        # optional fields: result, submitted, completed, expires
        self.node_id = 99
        self.action = _randomStr(10)
        self.payload = _gen_payload_obj()
        self.state = 'pending'
        self.result = _gen_result_obj()
        self.data = {'node_id': self.node_id,
                     'action': self.action,
                     'payload': self.payload,
                     'state': self.state,
                     'result': self.result}
        tmp = self.app.post('/tasks/',
                            content_type=self.content_type,
                            data=json.dumps(self.data))
        out = json.loads(tmp.data)
        self.task_id = out['task']['id']

    def tearDown(self):
        self.app.delete('/tasks/%s' % self.task_id,
                        content_type=self.content_type)

    def test_update_task_attribute_node_id(self):
        tmp_node_id = 11
        payload = {'node_id': tmp_node_id}
        resp = self.app.put('/tasks/%s' % self.task_id,
                            content_type=self.content_type,
                            data=json.dumps(payload))
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['task']['node_id'], tmp_node_id)
        self.assertNotEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], self.result)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        self.assertIsNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

    def test_update_task_attribute_action(self):
        tmp_action = _randomStr(10)
        payload = {'action': tmp_action}
        resp = self.app.put('/tasks/%s' % self.task_id,
                            content_type=self.content_type,
                            data=json.dumps(payload))
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], tmp_action)
        self.assertNotEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], self.result)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        self.assertIsNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

    def test_update_task_attribute_payload(self):
        tmp_payload = {_randomStr(5): _randomStr(10)}
        payload = {'payload': tmp_payload}
        resp = self.app.put('/tasks/%s' % self.task_id,
                            content_type=self.content_type,
                            data=json.dumps(payload))
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], tmp_payload)
        self.assertNotEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], self.result)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        self.assertIsNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

    def test_update_task_attribute_state(self):
        tmp_state = 'running'
        payload = {'state': tmp_state}
        resp = self.app.put('/tasks/%s' % self.task_id,
                            content_type=self.content_type,
                            data=json.dumps(payload))
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], tmp_state)
        self.assertNotEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], self.result)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        self.assertIsNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

    def test_update_task_attribute_state_to_terminal_value(self):
        # Setting tasks:state to a terminal value, should auto-update
        # the completed column
        tmp_state = 'done'
        payload = {'state': tmp_state}
        resp = self.app.put('/tasks/%s' % self.task_id,
                            content_type=self.content_type,
                            data=json.dumps(payload))
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], tmp_state)
        self.assertNotEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], self.result)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        # Make sure completed is now populated
        self.assertIsInstance(out['task']['completed'], int)
        self.assertIsNotNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

    def test_update_task_attribute_result(self):
        tmp_result = {_randomStr(5): _randomStr(10)}
        payload = {'result': tmp_result}
        resp = self.app.put('/tasks/%s' % self.task_id,
                            content_type=self.content_type,
                            data=json.dumps(payload))
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], tmp_result)
        self.assertNotEquals(out['task']['result'], self.result)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        self.assertIsNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

    def test_update_task_attribute_submitted(self):
        # This test should complete successfully, but
        # not actually modify the value of ['task']['submitted']
        tmp_submitted = int(time.time() + 120)  # add 2 mins
        payload = {'submitted': tmp_submitted}
        resp = self.app.put('/tasks/%s' % self.task_id,
                            content_type=self.content_type,
                            data=json.dumps(payload))
        self.assertEquals(resp.status_code, 200)
        out = json.loads(resp.data)
        self.assertEquals(out['task']['node_id'], self.node_id)
        self.assertEquals(out['task']['action'], self.action)
        self.assertEquals(out['task']['payload'], self.payload)
        self.assertEquals(out['task']['state'], self.state)
        self.assertEquals(out['task']['result'], self.result)
        # Make sure the update did not change the value
        self.assertNotEquals(out['task']['submitted'], tmp_submitted)
        self.assertIsInstance(out['task']['submitted'], int)
        self.assertIsNotNone(out['task']['submitted'])
        self.assertIsNone(out['task']['completed'])
        self.assertIsNone(out['task']['expires'])

    def test_update_task_attribute_completed_TODO(self):
        pass

    def test_update_task_attribute_expires_TODO(self):
        pass

    def test_update_task_with_no_data_returns_a_400(self):
        resp = self.app.put('/tasks/%s' % self.task_id,
                            data=None,
                            content_type=self.content_type)
        self.assertEquals(resp.status_code, 400)


class TaskInvalidHTTPMethodTests(unittest2.TestCase):
    @classmethod
    def setUpClass(self):
        self.foo = webapp.WebServer('opencenter',
                                    configfile='tests/test.conf',
                                    debug=True)
        self.app = self.foo.test_client()
        self.content_type = 'application/json'

    @classmethod
    def tearDownClass(self):
        pass

    def _execute_method(self, method_name, path, http_code):
        """Helper function that will execute a method, against a path and
           verify the returned http code

        :param method_name: name of the http method to execute
        :param path: path to execute the http call against
        :param http_code: http error code to validate against
        """
        resp = self.app.__getattribute__(method_name)(
            path,
            content_type=self.content_type)
        self.assertEquals(resp.status_code, http_code)

    def test_405_returned_by_delete_on_tasks(self):
        self._execute_method('delete', '/tasks/', 405)

    def test_405_returned_by_patch_on_tasks(self):
        self._execute_method('patch', '/tasks/', 405)

    def test_405_returned_by_put_on_tasks(self):
        self._execute_method('put', '/tasks/', 405)

    def test_405_returned_by_post_on_tasks_with_id(self):
        self._execute_method('post', '/tasks/99', 405)

    def test_405_returned_by_patch_on_tasks_with_id(self):
        self._execute_method('patch', '/tasks/99', 405)
