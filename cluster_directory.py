import os
import sys

import networkx as nx
import requests

BASE_URL = 'https://analyze.intezer.com/api/v2-0'
API_KEY = 'YOUR API KEY'


def get_session():
    response = requests.post(BASE_URL + '/get-access-token', json={'api_key': API_KEY})
    response.raise_for_status()
    session = requests.session()
    session.headers['Authorization'] = session.headers['Authorization'] = 'Bearer %s' % response.json()['result']
    return session


def send_to_analysis(file_path, session):
    with open(file_path, 'rb') as file_to_upload:
        files = {'file': ('file_name', file_to_upload)}
        response = session.post(BASE_URL + '/analyze', files=files)
        assert response.status_code == 201
        result_url = response.json()['result_url']
        return result_url


def analyze_directory(dir_path, session):
    result_urls = []
    results = []
    for path in os.listdir(dir_path):
        file_path = os.path.join(dir_path, path)
        if os.path.isfile(file_path):
            result_urls.append(send_to_analysis(file_path, session))

    while result_urls:
        result_url = result_urls.pop()
        response = session.get(BASE_URL + result_url)
        response.raise_for_status()
        if response.status_code != 200:
            result_urls.append(result_url)
        else:
            report = response.json()['result']
            results.append((report['sha256'], report['analysis_id']))

    return results


def send_to_related_samples(analysis_id, session):
    response = session.post(BASE_URL + '/analyses/{}/sub-analyses/root/get-account-related-samples'.format(analysis_id))
    assert response.status_code == 201
    result_url = response.json()['result_url']
    return result_url


def get_related_samples(results, session):
    result_urls = []
    previous_samples = {}
    for sha256, analysis_id in results:
        result_urls.append((sha256, send_to_related_samples(analysis_id, session)))

    while result_urls:
        sha256, result_url = result_urls.pop()
        response = session.get(BASE_URL + result_url)
        response.raise_for_status()
        if response.status_code != 200:
            result_urls.append((sha256, result_url))
        else:
            previous_samples[sha256] = response.json()['result']['related_samples']

    return previous_samples


def create_graph(previous_samples):
    g = nx.DiGraph()
    g.add_nodes_from(previous_samples)
    for sha256, related_samples in previous_samples.items():
        for analysis in related_samples:
            if analysis['analysis']['sha256'] in previous_samples:
                g.add_edge(sha256, analysis['analysis']['sha256'], gene_count=analysis['reused_genes']['gene_count'])

    return g


def main(dir_path):
    session = get_session()
    analyze_directory(dir_path, session)
    results = analyze_directory(dir_path, session)
    previous_samples = get_related_samples(results, session)
    create_graph(previous_samples)


if __name__ == '__main__':
    main(sys.argv[1])
