import time
import json
import re
import fisher
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import FloatVector
import os
import uuid
import errno
import csv
import zipfile

from Workspace.WorkspaceClient import Workspace as Workspace
from DataFileUtil.DataFileUtilClient import DataFileUtil
from KBaseReport.KBaseReportClient import KBaseReport
from GenomeSearchUtil.GenomeSearchUtilClient import GenomeSearchUtil


def log(message, prefix_newline=False):
    """Logging function, provides a hook to suppress or redirect log messages."""
    print(('\n' if prefix_newline else '') + '{0:.2f}'.format(time.time()) + ': ' + str(message))


class FunctionalEnrichmentUtil:

    def _mkdir_p(self, path):
        """
        _mkdir_p: make directory for given path
        """
        if not path:
            return
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    def _validate_run_fe1_params(self, params):
        """
        _validate_run_fe1_params:
                validates params passed to run_fe1 method
        """

        log('start validating run_fe1 params')

        # check for required parameters
        for p in ['feature_set_ref', 'workspace_name']:
            if p not in params:
                raise ValueError('"{}" parameter is required, but missing'.format(p))

    def _generate_report(self, enrichment_map, result_directory, workspace_name, 
                         feature_id_go_id_list_map, feature_set_ids, genome_ref, 
                         go_id_parent_ids_map, feature_ids):
        """
        _generate_report: generate summary report
        """

        log('start creating report')

        output_files = self._generate_output_file_list(result_directory,
                                                       enrichment_map,
                                                       feature_id_go_id_list_map,
                                                       feature_set_ids,
                                                       genome_ref,
                                                       go_id_parent_ids_map,
                                                       feature_ids)

        output_html_files = self._generate_html_report(result_directory,
                                                       enrichment_map)

        report_object_name = 'kb_functional_enrichment_1_report_' + str(uuid.uuid4())
        report_params = {'message': '',
                         'workspace_name': workspace_name,
                         'file_links': output_files,
                         'html_links': output_html_files,
                         'direct_html_link_index': 0,
                         'html_window_height': 333,
                         'report_object_name': report_object_name}

        kbase_report_client = KBaseReport(self.callback_url)
        output = kbase_report_client.create_extended_report(report_params)

        report_output = {'report_name': output['name'], 'report_ref': output['ref']}

        return report_output

    def _generate_supporting_files(self, result_directory, enrichment_map, 
                                   feature_id_go_id_list_map, feature_set_ids, genome_ref,
                                   go_id_parent_ids_map, feature_ids):
        """
        _generate_supporting_files: generate varies debug files 
        """
        supporting_files = list()

        feature_id_go_ids_map_file = os.path.join(result_directory, 'feature_id_go_ids_map.txt')
        go_id_feature_ids_map_file = os.path.join(result_directory, 'go_id_feature_ids_map.txt')
        feature_ids_file = os.path.join(result_directory, 'feature_ids.txt')
        feature_set_ids_file = os.path.join(result_directory, 'feature_set_ids.txt')
        fisher_variables_file = os.path.join(result_directory, 'fisher_variables.txt')
        genome_info_file = os.path.join(result_directory, 'genome_info.txt')
        go_id_parent_ids_map_file = os.path.join(result_directory, 'go_id_parent_ids_map.txt')

        supporting_files.append(feature_id_go_ids_map_file)
        supporting_files.append(go_id_feature_ids_map_file)
        supporting_files.append(feature_ids_file)
        supporting_files.append(feature_set_ids_file)
        supporting_files.append(fisher_variables_file)
        supporting_files.append(genome_info_file)
        supporting_files.append(go_id_parent_ids_map_file)

        total_feature_ids = feature_id_go_id_list_map.keys()
        feature_ids_with_feature = []
        for feature_id, go_ids in feature_id_go_id_list_map.iteritems():
            if isinstance(go_ids, list):
                feature_ids_with_feature.append(feature_id)
        genome_name = self.ws.get_object_info3({'objects': 
                                                [{'ref': genome_ref}]})['infos'][0][1]

        with open(go_id_parent_ids_map_file, 'wb') as go_id_parent_ids_map_file:
            for go_id, parent_ids in go_id_parent_ids_map.iteritems():
                go_id_parent_ids_map_file.write('{}: {}\n'.format(go_id, ', '.join(parent_ids)))

        with open(genome_info_file, 'wb') as genome_info_file:
            genome_info_file.write('genome_name: {}\n'.format(genome_name))
            genome_info_file.write('features: {}\n'.format(len(total_feature_ids)))
            genome_info_file.write('features with term: {}'.format(len(feature_ids_with_feature)))

        with open(feature_set_ids_file, 'wb') as feature_set_ids_file:
            feature_set_ids_file.write('\n'.join(feature_set_ids))

        with open(feature_id_go_ids_map_file, 'wb') as feature_id_go_ids_map_file:
            with open(feature_ids_file, 'wb') as feature_ids_file:
                for feature_id, go_ids in feature_id_go_id_list_map.iteritems():
                    if not re.match('.*\.\d*', feature_id):
                        feature_ids_file.write('{} {}\n'.format(feature_id,
                                                                feature_id in feature_set_ids))
                        if isinstance(go_ids, str):
                            feature_id_go_ids_map_file.write('{} {}\n'.format(feature_id, 
                                                                              go_ids))
                        else:
                            feature_id_go_ids_map_file.write('{} {}\n'.format(feature_id, 
                                                                              ', '.join(go_ids)))

        with open(go_id_feature_ids_map_file, 'wb') as go_id_feature_ids_map_file:
            with open(fisher_variables_file, 'wb') as fisher_variables_file:
                for go_id, go_info in enrichment_map.iteritems():
                    mapped_features = go_info.get('mapped_features')
                    go_id_feature_ids_map_file.write('{} {}\n'.format(go_id,
                                                                      ', '.join(mapped_features)))
                    a_value = go_info.get('num_in_subset_feature_set')
                    b_value = len(feature_set_ids) - a_value
                    c_value = len(mapped_features) - a_value
                    d_value = len(feature_ids) - len(feature_set_ids) - c_value
                    p_value = go_info.get('raw_p_value')
                    fisher_variables_file.write('{} a:{} b:{} c:{} d:{} '.format(go_id,
                                                                                 a_value,
                                                                                 b_value,
                                                                                 c_value,
                                                                                 d_value))
                    fisher_variables_file.write('p_value:{}\n'.format(p_value))

        result_file = os.path.join(result_directory, 'supporting_files.zip')
        with zipfile.ZipFile(result_file, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zip_file:
            for supporting_file in supporting_files:
                zip_file.write(supporting_file, 
                               os.path.basename(supporting_file))

        return [{'path': result_file,
                 'name': os.path.basename(result_file),
                 'label': os.path.basename(result_file),
                 'description': 'GO term functional enrichment supporting files'}]

    def _generate_output_file_list(self, result_directory, enrichment_map, 
                                   feature_id_go_id_list_map, feature_set_ids, genome_ref,
                                   go_id_parent_ids_map, feature_ids):
        """
        _generate_output_file_list: zip result files and generate file_links for report
        """

        log('start packing result files')
        output_files = list()

        result_file = os.path.join(result_directory, 'functional_enrichment.csv')
        with open(result_file, 'wb') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(['term_id', 'term', 'ontology', 'num_in_feature_set',
                             'num_in_ref_genome', 'raw_p_value', 'adjusted_p_value'])
            for key, value in enrichment_map.iteritems():
                writer.writerow([key, value['go_term'], value['namespace'],
                                 value['num_in_subset_feature_set'],
                                 value['num_in_ref_genome'], value['raw_p_value'],
                                 value['adjusted_p_value']])

        output_files.append({'path': result_file,
                             'name': os.path.basename(result_file),
                             'label': os.path.basename(result_file),
                             'description': 'GO term functional enrichment'})

        supporting_files = self._generate_supporting_files(result_directory, 
                                                           enrichment_map, 
                                                           feature_id_go_id_list_map,
                                                           feature_set_ids,
                                                           genome_ref,
                                                           go_id_parent_ids_map,
                                                           feature_ids)
        output_files += supporting_files

        return output_files

    def _generate_html_report(self, result_directory, enrichment_map):
        """
        _generate_html_report: generate html summary report
        """

        log('start generating html report')
        html_report = list()

        output_directory = os.path.join(self.scratch, str(uuid.uuid4()))
        self._mkdir_p(output_directory)
        result_file_path = os.path.join(output_directory, 'report.html')

        enrichment_table = ''
        data = csv.DictReader(open(os.path.join(result_directory, 'functional_enrichment.csv')), 
                              delimiter=',')
        sortedlist = sorted(data, key=lambda row: (row['raw_p_value'],
                                                   row['num_in_ref_genome']), 
                            reverse=True)

        for row in sortedlist:
            if row['num_in_feature_set'] != '0':
                enrichment_table += '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(*row.values())

        with open(result_file_path, 'w') as result_file:
            with open(os.path.join(os.path.dirname(__file__), 'report_template.html'),
                      'r') as report_template_file:
                report_template = report_template_file.read()
                report_template = report_template.replace('<tr>Enrichment_Table</tr>',
                                                          enrichment_table)
                result_file.write(report_template)

        report_shock_id = self.dfu.file_to_shock({'file_path': output_directory,
                                                  'pack': 'zip'})['shock_id']

        html_report.append({'shock_id': report_shock_id,
                            'name': os.path.basename(result_file_path),
                            'label': os.path.basename(result_file_path),
                            'description': 'HTML summary report for Functional Enrichment App'})
        return html_report

    def _get_go_maps_from_genome(self, genome_ref):
        """
        _search_genome: search genome data
        """

        log('start parsing GO terms from genome')

        feature_num = self.gsu.search({'ref': genome_ref})['num_found']

        genome_features = self.gsu.search({'ref': genome_ref,
                                           'limit': feature_num,
                                           'sort_by': [['feature_id', True]]})['features']

        feature_id_go_id_list_map = {}
        go_id_feature_id_list_map = {}
        go_id_go_term_map = {}
        feature_id_feature_info_map = {}

        for genome_feature in genome_features:
            feature_id = genome_feature.get('feature_id')
            feature_func = genome_feature.get('function')
            feature_type = genome_feature.get('feature_type')
            ontology_terms = genome_feature.get('ontology_terms')

            feature_id_feature_info_map.update({feature_id: {'function': feature_func,
                                                             'feature_type': feature_type}})

            go_id_list = []
            if ontology_terms:
                for ontology_id, ontology_term in ontology_terms.iteritems():
                    if re.match('[gG][oO]\:.*', ontology_id):
                        go_id_go_term_map.update({ontology_id: ontology_term})
                        go_id_list.append(ontology_id)

            if go_id_list:
                feature_id_go_id_list_map.update({feature_id: go_id_list})

                for go_id in go_id_list:
                    if go_id in go_id_feature_id_list_map:
                        feature_ids = go_id_feature_id_list_map.get(go_id)
                        feature_ids.append(feature_id)
                        go_id_feature_id_list_map.update({go_id: feature_ids})
                    else:
                        go_id_feature_id_list_map.update({go_id: [feature_id]})
            else:
                if not re.match('.*\.\d*', feature_id):
                    feature_id_go_id_list_map.update({feature_id: 'Unlabeled'})

        return (feature_id_go_id_list_map, go_id_feature_id_list_map,
                go_id_go_term_map, feature_id_feature_info_map)

    def _process_feature_set(self, feature_set_ref):
        """
        _process_feature_set: process FeatureSet object

        return:
        genome_ref: reference Genome object ref
        feature_set_ids: FeatureSet feature ids
        """

        log('start processing FeatureSet object')

        feature_set_data = self.ws.get_objects2({'objects':
                                                 [{'ref': feature_set_ref}]})['data'][0]['data']
        feature_elements = feature_set_data['elements']
        feature_set_ids = []
        genome_ref_array = []
        for feature_id, genome_refs in feature_elements.iteritems():
            feature_set_ids.append(feature_id)
            genome_ref_array += genome_refs

        if len(set(genome_ref_array)) > 1:
            error_msg = 'FeatureSet has multiple reference Genomes: {}'.format(genome_ref_array)
            raise ValueError(error_msg)

        return feature_set_ids, genome_ref_array[0]

    def _get_immediate_parents(self, ontology_hash, go_id, 
                               is_a_relationship, regulates_relationship, part_of_relationship):
        """
        _get_immediate_parents: get immediate parents go_ids for a given go_id
        """
        parent_ids = []
        antology_info = ontology_hash.get(go_id)

        if is_a_relationship:
            is_a_parents = antology_info.get('is_a')
            if is_a_parents:
                for parent_string in is_a_parents:
                    is_a_parent_id = parent_string.split('!')[0][:-1]
                    parent_ids.append(is_a_parent_id)

        if regulates_relationship:
            relationship = antology_info.get('relationship')
            if relationship:
                for relationship_string in relationship:
                    if relationship_string.split(' ')[0] == 'regulates':
                        parent_ids.append(relationship_string.split(' ')[1])

        if part_of_relationship:
            relationship = antology_info.get('relationship')
            if relationship:
                for relationship_string in relationship:
                    if relationship_string.split(' ')[0] == 'part_of':
                        parent_ids.append(relationship_string.split(' ')[1])

        return parent_ids

    def _fetch_all_parents_go_ids(self, ontology_hash, go_id, 
                                  is_a_relationship, regulates_relationship, part_of_relationship):
        """
        _fetch_all_parents_go_ids: recusively fetch all parent go_ids
        """

        parent_ids = self._get_immediate_parents(ontology_hash, go_id, 
                                                 is_a_relationship, regulates_relationship, 
                                                 part_of_relationship)
        if parent_ids:
            grand_parent_ids = parent_ids
            for parent_id in parent_ids:
                grand_parent_ids += self._fetch_all_parents_go_ids(ontology_hash, parent_id, 
                                                                   is_a_relationship, 
                                                                   regulates_relationship, 
                                                                   part_of_relationship)[parent_id]
            return {go_id: list(set(grand_parent_ids))}
        else:
            return {go_id: []}

    def _generate_parent_child_map(self, ontology_hash, go_ids, 
                                   is_a_relationship=True,
                                   regulates_relationship=True,
                                   part_of_relationship=False):
        """
        _generate_parent_child_map: fetch parent go_ids for given go_id
        """

        log('start fetching parent go_ids')
        start = time.time()

        go_id_parent_ids_map = {}
        
        for go_id in go_ids:
            fetch_result = self._fetch_all_parents_go_ids(ontology_hash, go_id, 
                                                          is_a_relationship, 
                                                          regulates_relationship, 
                                                          part_of_relationship)

            go_id_parent_ids_map.update(fetch_result) 

        end = time.time()
        print 'used {:.2f} s'.format(end - start)

        return go_id_parent_ids_map

    def __init__(self, config):
        self.ws_url = config['workspace-url']
        self.callback_url = config['SDK_CALLBACK_URL']
        self.token = config['KB_AUTH_TOKEN']
        self.shock_url = config['shock-url']
        self.scratch = config['scratch']
        self.dfu = DataFileUtil(self.callback_url)
        self.gsu = GenomeSearchUtil(self.callback_url)
        self.ws = Workspace(self.ws_url, token=self.token)

    def run_fe1(self, params):
        """
        run_fe1: Functional Enrichment One

        required params:
        feature_set_ref: FeatureSet object reference
        workspace_name: the name of the workspace it gets saved to      

        optional params:
        propagation: includes is_a relationship to all go terms (default is 1)
        filter_ref_features: filter reference genome features with no go terms (default is 0)

        return:
        result_directory: folder path that holds all files generated by run_deseq2_app
        report_name: report name generated by KBaseReport
        report_ref: report reference generated by KBaseReport
        """
        log('--->\nrunning FunctionalEnrichmentUtil.run_fe1\n' +
            'params:\n{}'.format(json.dumps(params, indent=1)))

        self._validate_run_fe1_params(params)
        propagation = params.get('propagation', True)
        filter_ref_features = params.get('filter_ref_features', False)

        result_directory = os.path.join(self.scratch, str(uuid.uuid4()))
        self._mkdir_p(result_directory)

        feature_set_ids, genome_ref = self._process_feature_set(params.get('feature_set_ref'))

        (feature_id_go_id_list_map, 
         go_id_feature_id_list_map,
         go_id_go_term_map, 
         feature_id_feature_info_map) = self._get_go_maps_from_genome(genome_ref)

        if filter_ref_features:
            log('start filtering featrues with no term')
            feature_ids = []
            for feature_id, go_ids in feature_id_go_id_list_map.iteritems():
                if isinstance(go_ids, list):
                    feature_ids.append(feature_id)
        else:
            feature_ids = feature_id_go_id_list_map.keys()

        ontology_hash = dict()
        ontologies = self.ws.get_objects([{'workspace': 'KBaseOntology',
                                           'name': 'gene_ontology'},
                                          {'workspace': 'KBaseOntology',
                                           'name': 'plant_ontology'}])
        ontology_hash.update(ontologies[0]['data']['term_hash'])
        ontology_hash.update(ontologies[1]['data']['term_hash'])

        if propagation:
            go_id_parent_ids_map = self._generate_parent_child_map(ontology_hash, 
                                                                   go_id_go_term_map.keys(),
                                                                   regulates_relationship=False)
        else:
            go_id_parent_ids_map = {}
            for go_id in go_id_go_term_map.keys():
                go_id_parent_ids_map.update({go_id: []})

        log('including parents to feature id map')
        for go_id, parent_ids in go_id_parent_ids_map.iteritems():
            mapped_features = go_id_feature_id_list_map.get(go_id)

            for parent_id in parent_ids:
                parent_mapped_features = go_id_feature_id_list_map.get(parent_id)

                if not parent_mapped_features:
                    parent_mapped_features = []

                if mapped_features:
                    parent_mapped_features += mapped_features

                go_id_feature_id_list_map.update({parent_id: list(set(parent_mapped_features))})

        log('start calculating p-values')
        enrichment_map = {}
        go_info_map = {}
        all_raw_p_value = []
        pos = 0
        for go_id, go_term in go_id_go_term_map.iteritems():
            mapped_features = go_id_feature_id_list_map.get(go_id)
            # in feature_set matches go_id
            a = len(set(mapped_features).intersection(feature_set_ids))
            # in feature_set doesn't match go_id
            b = len(feature_set_ids) - a
            # not in feature_set matches go_id
            c = len(mapped_features) - a
            # not in feature_set doesn't match go_id
            d = len(feature_ids) - len(feature_set_ids) - c

            raw_p_value = fisher.pvalue(a, b, c, d).two_tail
            all_raw_p_value.append(raw_p_value)
            go_info_map.update({go_id: {'raw_p_value': raw_p_value,
                                        'num_in_ref_genome': len(mapped_features),
                                        'num_in_subset_feature_set': a,
                                        'pos': pos,
                                        'mapped_features': mapped_features}})
            pos += 1

        stats = importr('stats')
        adjusted_p_values = stats.p_adjust(FloatVector(all_raw_p_value), method='fdr')

        for go_id, go_info in go_info_map.iteritems():
            adjusted_p_value = adjusted_p_values[go_info.get('pos')]
            namespace = ontology_hash[go_id]['namespace']
            enrichment_map.update({go_id: {'raw_p_value': go_info.get('raw_p_value'),
                                           'adjusted_p_value': adjusted_p_value,
                                           'num_in_ref_genome': go_info.get('num_in_ref_genome'),
                                           'num_in_subset_feature_set': 
                                           go_info.get('num_in_subset_feature_set'),
                                           'go_term': go_id_go_term_map.get(go_id),
                                           'namespace': namespace.split("_")[1][0].upper(),
                                           'mapped_features': go_info.get('mapped_features')}})

        returnVal = {'result_directory': result_directory}
        report_output = self._generate_report(enrichment_map,
                                              result_directory,
                                              params.get('workspace_name'),
                                              feature_id_go_id_list_map,
                                              feature_set_ids,
                                              genome_ref,
                                              go_id_parent_ids_map,
                                              feature_ids)

        returnVal.update(report_output)

        return returnVal
