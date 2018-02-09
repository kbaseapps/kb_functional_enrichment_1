# -*- coding: utf-8 -*-
import unittest
import os  # noqa: F401
import json  # noqa: F401
import time
import requests  # noqa: F401
import shutil
import csv

from os import environ
try:
    from ConfigParser import ConfigParser  # py2
except:
    from configparser import ConfigParser  # py3

from pprint import pprint  # noqa: F401

from biokbase.workspace.client import Workspace as workspaceService
from Workspace.WorkspaceClient import Workspace as Workspace
from kb_functional_enrichment_1.kb_functional_enrichment_1Impl import kb_functional_enrichment_1
from kb_functional_enrichment_1.kb_functional_enrichment_1Server import MethodContext
from kb_functional_enrichment_1.authclient import KBaseAuth as _KBaseAuth
from kb_functional_enrichment_1.Utils.FunctionalEnrichmentUtil import FunctionalEnrichmentUtil
from GenomeFileUtil.GenomeFileUtilClient import GenomeFileUtil
from DataFileUtil.DataFileUtilClient import DataFileUtil


class kb_functional_enrichment_1Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = environ.get('KB_AUTH_TOKEN', None)
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('kb_functional_enrichment_1'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'kb_functional_enrichment_1',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = workspaceService(cls.wsURL)
        cls.serviceImpl = kb_functional_enrichment_1(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']

        cls.fe1_runner = FunctionalEnrichmentUtil(cls.cfg)
        cls.gfu = GenomeFileUtil(cls.callback_url)
        cls.dfu = DataFileUtil(cls.callback_url)
        cls.ws = Workspace(cls.wsURL, token=token)

        suffix = int(time.time() * 1000)
        cls.wsName = "test_kb_functional_enrichment_1_" + str(suffix)
        cls.wsClient.create_workspace({'workspace': cls.wsName})

        cls.prepare_data()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    @classmethod
    def prepare_data(cls):
        # upload genome object
        genbank_file_name = 'minimal.gbff'
        genbank_file_path = os.path.join(cls.scratch, genbank_file_name)
        shutil.copy(os.path.join('data', genbank_file_name), genbank_file_path)

        genome_object_name = 'test_Genome'
        cls.genome_ref = cls.gfu.genbank_to_genome({'file': {'path': genbank_file_path},
                                                    'workspace_name': cls.wsName,
                                                    'genome_name': genome_object_name
                                                    })['genome_ref']

        # upload feature set object
        test_feature_set_name = 'MyFeatureSet'
        test_feature_set_data = {'description': 'Generated FeatureSet from DifferentialExpression',
                                 'element_ordering': ['b1', 'b2'],
                                 'elements': {'b1': [cls.genome_ref],
                                              'b2': [cls.genome_ref]}}

        save_object_params = {
            'id': cls.dfu.ws_name_to_id(cls.wsName),
            'objects': [{'type': 'KBaseCollections.FeatureSet',
                         'data': test_feature_set_data,
                         'name': test_feature_set_name}]
        }

        dfu_oi = cls.dfu.save_objects(save_object_params)[0]
        cls.feature_set_ref = str(dfu_oi[6]) + '/' + str(dfu_oi[0]) + '/' + str(dfu_oi[4])

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        return self.__class__.wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def test_bad_run_fe1_params(self):
        invalidate_input_params = {'missing_feature_set_ref': 'feature_set_ref',
                                   'workspace_name': 'workspace_name'}
        with self.assertRaisesRegexp(ValueError, 
                                     '"feature_set_ref" parameter is required, but missing'):
            self.getImpl().run_fe1(self.getContext(), invalidate_input_params)

        invalidate_input_params = {'feature_set_ref': 'feature_set_ref',
                                   'missing_workspace_name': 'workspace_name'}
        with self.assertRaisesRegexp(ValueError, 
                                     '"workspace_name" parameter is required, but missing'):
            self.getImpl().run_fe1(self.getContext(), invalidate_input_params)

    def test_run_fe1(self):

        input_params = {
            'feature_set_ref': self.feature_set_ref,
            'workspace_name': self.getWsName(),
            'propagation': 0,
            'filter_ref_features': 1
        }

        result = self.getImpl().run_fe1(self.getContext(), input_params)[0]

        self.assertTrue('result_directory' in result)
        result_files = os.listdir(result['result_directory'])
        print(result_files)
        expect_result_files = ['functional_enrichment.csv']
        self.assertTrue(all(x in result_files for x in expect_result_files))

        with open(os.path.join(result['result_directory'], 
                  'functional_enrichment.csv'), 'rb') as f:
            reader = csv.reader(f)
            header = reader.next()
            expected_header = ['term_id', 'term', 'ontology', 'num_in_feature_set',
                               'num_in_ref_genome', 'raw_p_value', 'adjusted_p_value']
            self.assertTrue(all(x in header for x in expected_header))

        self.assertTrue('report_name' in result)
        self.assertTrue('report_ref' in result)
