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
import operator

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
        for p in ['genome_ref', 'workspace_name']:
            if p not in params:
                raise ValueError('"{}" parameter is required, but missing'.format(p))

    def _generate_report(self, enrichment_map, result_directory, workspace_name):
        """
        _generate_report: generate summary report
        """
        log('creating report')

        output_files = self._generate_output_file_list(result_directory,
                                                       enrichment_map)

        output_html_files = self._generate_html_report(result_directory,
                                                       enrichment_map)

        report_params = {
              'message': '',
              'workspace_name': workspace_name,
              'file_links': output_files,
              'html_links': output_html_files,
              'direct_html_link_index': 0,
              'html_window_height': 333,
              'report_object_name': 'kb_functional_enrichment_1_report_' + str(uuid.uuid4())}

        kbase_report_client = KBaseReport(self.callback_url)
        output = kbase_report_client.create_extended_report(report_params)

        report_output = {'report_name': output['name'], 'report_ref': output['ref']}

        return report_output

    def _generate_output_file_list(self, result_directory, enrichment_map):
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
        data = csv.reader(open(os.path.join(result_directory, 'functional_enrichment.csv')),
                          delimiter=',')
        data.next()
        sortedlist = sorted(data, key=operator.itemgetter(5), reverse=True)
        for row in sortedlist[:20]:
            enrichment_table += '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(*row)

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

        return (feature_id_go_id_list_map, go_id_feature_id_list_map,
                go_id_go_term_map, feature_id_feature_info_map)

    def _get_feature_set_ids(self):
        """
        _get_feature_set_ids: get subset feature ids from FeatureSet
        """
        log('start generating feature set ids')
        feature_set_ids = ['AT1G01010', 'AT1G01030', 'AT1G01020', 'AT1G01050', 'AT1G01060']
        # feature_set_ids = ['AT5G42530', 'AT4G28080', 'AT2G25510', 'AT1G01320', 'AT3G25690', 'AT1G10760', 'AT5G22640', 'AT2G01021', 'AT4G24190', 'AT1G55860', 'AT2G03965', 'AT4G26630', 'AT4G10120', 'AT3G01345', 'AT1G20920', 'AT4G20850', 'AT3G18390', 'AT1G70320', 'AT3G24080', 'AT2G05914', 'AT2G41090', 'AT4G17330', 'AT2G25660', 'AT5G55660', 'AT1G64790', 'AT1G26150', 'AT2G28290', 'AT1G21250', 'AT1G79830', 'AT1G76810', 'AT1G12800', 'AT3G25840', 'AT1G48090', 'AT2G32240', 'AT3G06400', 'AT4G11420', 'AT4G13510', 'AT3G29320', 'AT5G04290', 'AT1G58602', 'AT5G09880', 'AT4G17140', 'AT1G80930', 'AT5G47690', 'AT5G41790', 'AT1G22610', 'AT1G21580', 'AT4G18240', 'AT3G47910', 'AT2G14610', 'AT2G35630', 'AT1G67230', 'AT1G03060', 'AT1G02080', 'AT1G70620', 'AT1G79280', 'AT3G49601', 'AT1G50030', 'AT1G59218', 'AT5G08450', 'AT2G17930', 'AT2G46020', 'AT4G36980', 'AT3G16000', 'AT5G20490', 'AT1G60200', 'AT1G02930', 'AT4G12490', 'AT5G44180', 'AT1G02920', 'AT5G47500', 'AT4G02260', 'AT2G25730', 'AT5G56360', 'AT3G04340', 'AT5G63530', 'AT4G33740', 'AT5G61150', 'AT5G56850', 'AT2G03150', 'AT1G58250', 'AT5G27330', 'AT1G14610', 'AT3G54760', 'AT3G16290', 'AT5G35210', 'AT5G55300', 'AT5G24620', 'AT4G14400', 'AT5G66030', 'AT2G11225', 'AT1G20970', 'AT5G16780', 'AT5G10470', 'AT5G47820', 'AT3G48110', 'AT5G61140', 'AT1G79000', 'AT4G23800', 'AT1G10320', 'AT1G24706', 'AT3G50950', 'AT1G44910', 'AT4G10060', 'AT3G57300', 'AT2G39580', 'AT1G71220', 'AT1G76960', 'AT4G15180', 'AT5G13010', 'AT1G15200', 'AT3G44265', 'AT1G03080', 'AT5G44800', 'AT5G02810', 'AT1G70060', 'AT5G16030', 'AT1G14880', 'AT1G24460', 'AT5G55310', 'AT1G65010', 'AT4G37460', 'AT3G23070', 'AT3G57470', 'AT2G46560', 'AT1G74250', 'AT4G31570', 'AT5G16730', 'AT1G28420', 'AT3G51150', 'AT1G58848', 'AT1G79380', 'AT5G43560', 'AT5G25060', 'AT5G43900', 'AT1G15780', 'AT3G54280', 'AT1G80790', 'AT5G64580', 'AT5G42600', 'AT5G42540', 'AT2G21380', 'AT4G29900', 'AT3G48670', 'AT3G01370', 'AT2G39260', 'AT2G25170', 'AT5G23110', 'AT3G16840', 'AT2G27170', 'AT3G45850', 'AT2G19110', 'AT4G26190', 'AT1G50660', 'AT2G42270', 'AT5G08420', 'AT3G23890', 'AT5G23240', 'AT5G27970', 'AT5G53440', 'AT3G06430', 'AT1G70610', 'AT1G01040', 'AT3G12810', 'AT4G31880', 'AT4G16660', 'AT3G62900', 'AT1G19835', 'AT3G54010', 'AT1G53510', 'AT4G02400', 'AT3G14172', 'AT1G50840', 'AT1G17990', 'AT1G59890', 'AT1G11720', 'AT1G04300', 'AT3G09920', 'AT1G32750', 'AT5G67320', 'AT2G13370', 'AT1G58200', 'AT3G44480', 'AT1G17110', 'AT2G03140', 'AT3G29390', 'AT5G02880', 'AT5G65210', 'AT4G27180', 'AT1G72410', 'AT4G04740', 'AT3G44670', 'AT5G10760', 'AT1G17360', 'AT3G06345', 'AT5G44120', 'AT5G35660', 'AT5G40340', 'AT1G53430', 'AT1G65800', 'AT4G38120', 'AT4G08593', 'AT2G22300', 'AT1G35710', 'AT3G24518', 'AT2G48120', 'AT2G15880', 'AT5G02940', 'AT1G53780', 'AT2G41700', 'AT2G33051', 'AT4G02020', 'AT2G06562', 'AT4G39050', 'AT1G33960', 'AT2G33435', 'AT1G10130', 'AT3G19720', 'AT3G22530', 'AT4G32330', 'AT1G62310', 'AT4G00990', 'AT5G25560', 'AT3G50380', 'AT5G16210', 'AT4G36080', 'AT3G44070', 'AT1G53800', 'AT1G30410', 'AT5G55100', 'AT5G08390', 'AT5G22080', 'AT3G05060', 'AT2G40430', 'AT4G12610', 'AT3G16340', 'AT1G13120', 'AT5G17440', 'AT4G07965', 'AT5G27950', 'AT1G66840', 'AT5G45570', 'AT1G26390', 'AT2G32170', 'AT4G10930', 'AT4G14760', 'AT2G18193', 'AT2G14120', 'AT1G67140', 'AT3G06930', 'AT2G18230', 'AT2G39340', 'AT1G68790', 'AT5G16680', 'AT4G32190', 'AT1G67120', 'AT1G77300', 'AT4G37560', 'AT1G16710', 'AT5G15360', 'AT4G33500', 'AT2G40360', 'AT2G32950', 'AT4G37820', 'AT2G47410', 'AT1G24190', 'AT1G21160', 'AT5G13730', 'AT2G21440', 'AT3G54670', 'AT5G10910', 'AT5G04560', 'AT4G28710', 'AT1G25540', 'AT1G78970', 'AT1G79350', 'AT3G07050', 'AT4G36520', 'AT3G05270', 'AT4G38760', 'AT5G08080', 'AT1G64330', 'AT2G48060', 'AT1G62850', 'AT4G33060', 'AT1G21700', 'AT4G29200', 'AT1G77930', 'AT3G47890', 'AT2G41350', 'AT1G10450', 'AT3G52180', 'AT3G52030', 'AT1G65370', 'AT3G05380', 'AT3G48120', 'AT4G06643', 'AT3G05130', 'AT4G09020', 'AT1G09980', 'AT5G15540', 'AT5G42400', 'AT1G69070', 'AT5G55820', 'AT2G14680', 'AT3G20550', 'AT5G03420', 'AT4G38950', 'AT5G16280', 'AT5G65440', 'AT2G28780', 'AT4G24810', 'AT5G43745', 'AT4G14330', 'AT3G14205', 'AT1G13350', 'AT3G50480', 'AT1G10890', 'AT4G33270', 'AT3G18480', 'AT5G49930', 'AT5G22760', 'AT3G46130', 'AT2G44950', 'AT5G27120', 'AT1G58230', 'AT4G16280', 'AT3G01320', 'AT4G23940', 'AT1G33360', 'AT5G13840', 'AT1G13220', 'AT5G08370', 'AT5G01290', 'AT3G22790', 'AT2G17820', 'AT5G17160', 'AT1G58060', 'AT5G66310', 'AT1G56290', 'AT4G37920', 'AT3G57230', 'AT5G38840', 'AT2G43570', 'AT5G65460', 'AT1G78580', 'AT3G13225', 'AT5G52550', 'AT4G29750', 'AT4G04350', 'AT3G21290', 'AT4G32660', 'AT1G80810', 'AT5G04935', 'AT5G41020', 'AT2G34357', 'AT5G06120', 'AT5G26610', 'AT4G39160', 'AT5G13690', 'AT1G17690', 'AT1G15910', 'AT5G48600', 'AT5G10950', 'AT1G26230', 'AT1G21610', 'AT1G03780', 'AT1G14460', 'AT3G61420', 'AT5G55520', 'AT4G08470', 'AT5G66540', 'AT1G56460', 'AT2G45730', 'AT2G18250', 'AT1G08060', 'AT1G18190', 'AT5G04965', 'AT5G05005', 'AT1G19220', 'AT4G34900', 'AT3G19650', 'AT4G32420', 'AT4G12020', 'AT5G60100', 'AT4G27120', 'AT2G38580', 'AT1G79950', 'AT1G63100', 'AT5G44750', 'AT4G12460', 'AT3G59820', 'AT4G09680', 'AT1G73960', 'AT1G64570', 'AT5G52790', 'AT5G44870', 'AT2G18660', 'AT1G65070', 'AT1G70250', 'AT5G57960', 'AT5G45260', 'AT5G38150', 'AT5G19310', 'AT1G15520', 'AT2G16750', 'AT2G42540', 'AT1G49570', 'AT1G65500', 'AT2G18220', 'AT4G04030', 'AT3G21810', 'AT3G62300', 'AT1G75310', 'AT3G48190', 'AT5G61190', 'AT2G24650', 'AT4G00040', 'AT5G45060', 'AT2G25480', 'AT5G52300', 'AT5G60250', 'AT1G77920', 'AT5G13480', 'AT5G62760', 'AT3G27670', 'AT4G16765', 'AT2G41520', 'AT4G26140', 'AT5G56210', 'AT1G15940', 'AT1G72650', 'AT1G75100', 'AT5G37190', 'AT5G63880', 'AT1G03950', 'AT2G17040', 'AT4G32820', 'AT3G24870', 'AT4G23260', 'AT1G65470', 'AT5G01080', 'AT4G15450', 'AT4G28520', 'AT2G39375', 'AT2G27470', 'AT3G59100', 'AT3G20150', 'AT4G16630', 'AT1G17232', 'AT3G19670', 'AT4G02710', 'AT1G05840', 'AT1G73450', 'AT2G19950', 'AT1G78010', 'AT1G10870', 'AT1G17520', 'AT2G37840', 'AT3G19080', 'AT2G34260', 'AT5G67240', 'AT1G51800', 'AT1G72250', 'AT4G36400', 'AT5G49880', 'AT4G15130', 'AT5G58510', 'AT3G52280', 'AT2G29720', 'AT4G33200', 'AT3G04770', 'AT1G19485', 'AT3G50240', 'AT5G37350', 'AT4G02110', 'AT5G46520', 'AT3G01260', 'AT2G26560', 'AT1G27921', 'AT5G04995', 'AT5G56660', 'AT3G26380', 'AT1G77580', 'AT4G16680', 'AT4G13040', 'AT4G38545', 'AT4G02390', 'AT1G49870', 'AT5G44510', 'AT3G06465', 'AT1G09230', 'AT5G10270', 'AT3G03300', 'AT4G30900', 'AT2G18876', 'AT2G46440', 'AT3G55850', 'AT4G34140', 'AT2G28250', 'AT2G30750', 'AT5G08760', 'AT3G57940', 'AT1G30640', 'AT3G11010', 'AT5G61040', 'AT3G22760', 'AT5G56790', 'AT5G06960', 'AT1G60640', 'AT4G00670', 'AT1G77600', 'AT1G52410', 'AT3G02850', 'AT3G53760', 'AT5G54610', 'AT1G26170', 'AT1G05900', 'AT3G50110', 'AT3G44050', 'AT1G55250', 'AT1G16630', 'AT4G14365', 'AT1G30420', 'AT2G05210', 'AT1G55750', 'AT2G02170', 'AT1G01448', 'AT3G04160', 'AT1G43815', 'AT1G09090', 'AT2G28490', 'AT1G07910', 'AT5G67530', 'AT2G31530', 'AT2G42330', 'AT1G20410', 'AT3G19840', 'AT2G45920', 'AT3G53090', 'AT5G63950', 'AT1G68990', 'AT4G05205', 'AT5G57830', 'AT5G04985', 'AT4G37480', 'AT3G28510', 'AT5G07680', 'AT2G31970', 'AT2G34780', 'AT5G57410', 'AT4G01550', 'AT5G63700', 'AT3G56690', 'AT5G48340', 'AT1G63780', 'AT4G16845', 'AT1G69010', 'AT3G07520', 'AT1G73720', 'AT5G63220', 'AT3G14670', 'AT3G05830', 'AT1G63640', 'AT1G57700', 'AT5G51840', 'AT5G44635', 'AT5G43500', 'AT2G27380', 'AT3G25010', 'AT2G36200', 'AT5G65400', 'AT4G05715', 'AT2G29090', 'AT1G09023', 'AT1G64572', 'AT1G02010', 'AT2G36740', 'AT4G37280', 'AT3G27610', 'AT1G34340', 'AT4G15242', 'AT5G07820', 'AT3G19050', 'AT3G45443', 'AT1G50730', 'AT4G38062', 'AT4G13750', 'AT3G23740', 'AT3G25719', 'AT3G56020', 'AT2G45180', 'AT1G79075', 'AT1G56045', 'AT5G03545', 'AT1G29920', 'AT2G05440', 'AT1G22690', 'AT3G08520', 'AT5G20790', 'AT5G28450', 'AT2G34585', 'AT3G11120', 'AT1G06463', 'AT5G21020', 'AT1G49245', 'AT3G06900', 'AT3G16660', 'AT1G75750', 'AT5G47890', 'AT5G41471', 'AT1G09333', 'AT5G59030', 'AT2G05540', 'AT2G23670', 'AT4G04615', 'AT3G14735', 'AT3G13855', 'AT5G46315', 'AT5G38650', 'AT5G42110', 'AT1G10682', 'AT2G07605', 'AT5G07322', 'AT5G13930', 'AT3G43110', 'AT3G57020', 'AT3G06390', 'AT3G54366', 'AT5G10100', 'AT5G43370', 'AT4G14010', 'AT1G48750', 'AT5G04305', 'AT4G02270', 'AT3G14430', 'AT2G38940', 'AT1G28200', 'AT1G09937', 'AT2G03090', 'AT3G06125', 'AT4G20390', 'AT5G20410', 'AT1G77120', 'AT1G04263', 'AT4G38932', 'AT1G05853', 'AT5G04085', 'AT1G70185', 'AT4G13395', 'AT5G57785', 'AT3G09922', 'AT5G44110', 'AT5G02502', 'AT4G09135', 'AT5G04465', 'AT3G51240', 'AT1G57770', 'AT5G05060', 'AT1G19200', 'AT2G27330', 'AT4G04840', 'AT4G33560', 'AT5G65860', 'AT1G29071', 'AT2G33050', 'AT1G26218', 'AT4G33070', 'AT5G15960', 'AT2G08825', 'AT1G43800', 'AT2G24040', 'AT1G21110', 'AT3G05335', 'AT3G17790', 'AT3G13677', 'AT5G52250', 'AT5G01075', 'AT2G16060', 'AT1G47400', 'AT3G09455', 'AT3G27030', 'AT1G30840', 'AT5G25830', 'AT1G47395', 'AT2G43920', 'AT5G66985', 'AT3G08665', 'AT1G06253', 'AT5G08640', 'AT5G10140', 'AT4G13235', 'AT2G26830', 'AT4G10330', 'AT2G08820', 'AT4G28280', 'AT3G14340', 'AT1G75880', 'AT5G63140', 'AT1G09240', 'AT5G20120', 'AT5G03553', 'AT5G24850', 'AT2G46880', 'AT4G31940', 'AT5G54530', 'AT2G09700', 'AT3G02445', 'AT3G24450', 'AT5G09480', 'AT1G70350', 'AT5G42470', 'AT5G65925', 'AT3G06890', 'AT5G37690', 'AT1G11740', 'AT5G23710', 'AT1G32310', 'AT5G15022', 'AT3G59890', 'AT3G46490', 'AT2G32487', 'AT4G01060', 'AT5G07105', 'AT1G65420', 'AT1G48315', 'AT1G52050', 'AT2G45130', 'AT5G62520', 'AT3G07735']
        return feature_set_ids

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
        genome_ref: Genome object reference
        workspace_name: the name of the workspace it gets saved to

        return:
        result_directory: folder path that holds all files generated by run_deseq2_app
        report_name: report name generated by KBaseReport
        report_ref: report reference generated by KBaseReport
        """
        log('--->\nrunning FunctionalEnrichmentUtil.run_fe1\n' +
            'params:\n{}'.format(json.dumps(params, indent=1)))

        self._validate_run_fe1_params(params)

        result_directory = os.path.join(self.scratch, str(uuid.uuid4()))
        self._mkdir_p(result_directory)

        genome_ref = params.get('genome_ref')
        (feature_id_go_id_list_map, go_id_feature_id_list_map,
         go_id_go_term_map, feature_id_feature_info_map) = self._get_go_maps_from_genome(genome_ref)

        feature_set_ids = self._get_feature_set_ids()
        feature_ids = feature_id_feature_info_map.keys()

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

            raw_p_value = fisher.pvalue(a, b, c, d).left_tail
            all_raw_p_value.append(raw_p_value)
            go_info_map.update({go_id: {'raw_p_value': raw_p_value,
                                        'num_in_ref_genome': len(mapped_features),
                                        'num_in_subset_feature_set': a,
                                        'pos': pos}})
            pos += 1

        stats = importr('stats')
        adjusted_p_values = stats.p_adjust(FloatVector(all_raw_p_value), method='fdr')

        ontologies = self.ws.get_objects([{'workspace': 'KBaseOntology',
                                           'name': 'gene_ontology'},
                                          {'workspace': 'KBaseOntology',
                                           'name': 'plant_ontology'}])

        ontology_hash = dict()
        ontology_hash.update(ontologies[0]['data']['term_hash'])
        ontology_hash.update(ontologies[1]['data']['term_hash'])

        for go_id, go_info in go_info_map.iteritems():
            adjusted_p_value = adjusted_p_values[go_info.get('pos')]
            namespace = ontology_hash[go_id]['namespace']
            enrichment_map.update({go_id: {'raw_p_value': go_info.get('raw_p_value'),
                                           'adjusted_p_value': adjusted_p_value,
                                           'num_in_ref_genome': go_info.get('num_in_ref_genome'),
                                           'num_in_subset_feature_set': go_info.get(
                                                                    'num_in_subset_feature_set'),
                                           'go_term': go_id_go_term_map.get(go_id),
                                           'namespace': namespace.split("_")[1][0].upper()}})

        returnVal = {'result_directory': result_directory}
        report_output = self._generate_report(enrichment_map,
                                              result_directory,
                                              params.get('workspace_name'))

        returnVal.update(report_output)

        return returnVal
