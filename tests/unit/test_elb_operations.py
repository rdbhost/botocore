#!/usr/bin/env python
# Copyright (c) 2012-2013 Mitch Garnaat http://garnaat.org/
# Copyright 2012-2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.


#
#  This file altered by David Keeney 2015, as part of conversion to
# asyncio.
#
import os
os.environ['PYTHONASYNCIODEBUG'] = 1
import logging
logging.basicConfig(level=logging.DEBUG)

import asyncio
import sys
sys.path.append('..')
from asyncio_test_utils import async_test

from tests import TestParamSerialization
import yieldfrom.botocore.session


class TestELBOperations(TestParamSerialization):

    @async_test
    def test_describe_load_balancers_no_params(self):
        params = {}
        result = {}
        yield from self.assert_params_serialize_to('elb.DescribeLoadBalancers', params, result)

    @async_test
    def test_describe_load_balancers_name(self):
        params = dict(load_balancer_names=['foo'])
        result = {'LoadBalancerNames.member.1': 'foo'}
        yield from self.assert_params_serialize_to('elb.DescribeLoadBalancers', params, result)

    @async_test
    def test_describe_load_balancers_names(self):
        params = dict(load_balancer_names=['foo', 'bar'])
        result = {'LoadBalancerNames.member.1': 'foo',
                  'LoadBalancerNames.member.2': 'bar'}
        yield from self.assert_params_serialize_to('elb.DescribeLoadBalancers', params, result)

    @async_test
    def test_create_load_balancer_listeners(self):
        params = dict(listeners=[{'InstancePort':80,
                                                 'SSLCertificateId': 'foobar',
                                                 'LoadBalancerPort':81,
                                                 'Protocol':'HTTPS',
                                                 'InstanceProtocol':'HTTP'}],
                                     load_balancer_name='foobar')
        result = {'Listeners.member.1.LoadBalancerPort': 81,
                  'Listeners.member.1.InstancePort': 80,
                  'Listeners.member.1.Protocol': 'HTTPS',
                  'Listeners.member.1.InstanceProtocol': 'HTTP',
                  'Listeners.member.1.SSLCertificateId': 'foobar',
                  'LoadBalancerName': 'foobar'}
        yield from self.assert_params_serialize_to('elb.CreateLoadBalancerListeners', params, result)

    @async_test
    def test_register_instances_with_load_balancer(self):
        params = dict(load_balancer_name='foobar',
                                     instances=[{'InstanceId': 'i-12345678'},
                                                {'InstanceId': 'i-87654321'}])
        result = {'LoadBalancerName': 'foobar',
                  'Instances.member.1.InstanceId': 'i-12345678',
                  'Instances.member.2.InstanceId': 'i-87654321'}
        yield from self.assert_params_serialize_to('elb.RegisterInstancesWithLoadBalancer', params, result)

    @async_test
    def test_set_lb_policies_for_backend_server(self):
        params = dict(load_balancer_name='foobar',
                                     instance_port=443,
                                     policy_names=['fie', 'baz'])
        result = {'LoadBalancerName': 'foobar',
                  'InstancePort': 443,
                  'PolicyNames.member.1': 'fie',
                  'PolicyNames.member.2': 'baz'}
        yield from self.assert_params_serialize_to('elb.SetLoadBalancerPoliciesForBackendServer', params, result)

    @async_test
    def test_clear_lb_policies_for_backend_server(self):
        params = dict(load_balancer_name='foobar', instance_port=443,
                      policy_names=[])
        result = {'LoadBalancerName': 'foobar',
                  'InstancePort': 443,
                  'PolicyNames': ''}
        yield from self.assert_params_serialize_to('elb.SetLoadBalancerPoliciesForBackendServer', params, result)


if __name__ == "__main__":
    unittest.main()
