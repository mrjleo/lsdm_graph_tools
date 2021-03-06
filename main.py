#! /usr/bin/python
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from graph import Graph
from collections import deque
import json
import sys
import time
import math


def show_progress(current, total):
	sys.stdout.write('\r{}%\t[{}/{}]'.format(int(100 * current / total), current, total))
	sys.stdout.flush()


def less_than(g, v_idx, w_idx):
	return g.degree(v_idx) < g.degree(w_idx) or g.degree(v_idx) == g.degree(w_idx) and v_idx < w_idx


def count_triangles(graph):
	verts = graph.get_verts()
	trias = dict.fromkeys(verts, 0)

	# partition nodes in heavy hitters and normal nodes
	nodes = []
	hh_nodes = []
	hh_deg = math.sqrt(graph.u_edge_count)
	print('min. degree for heavy hitters: sqrt(m) = {}'.format(hh_deg))
	for v in verts:
		if graph.degree(v) > hh_deg:
			hh_nodes.append(v)
		else:
			nodes.append(v)
	print('found {} heavy hitter(s)'.format(len(hh_nodes)))

	# for progess indicator
	total = len(verts)
	current = 0

	# count heavy-hitter triangles
	for v in hh_nodes:
		for u in hh_nodes:
			for w in hh_nodes:
				if graph.is_directed_edge([v, u]) and graph.is_directed_edge([u, w]) and graph.is_directed_edge([w, v]):
					trias[v] += 1
		
		current += 1
		show_progress(current, total)

	# count rest of triangles
	for v in nodes:
		for w in verts:
			if graph.is_directed_edge([v, w]) and less_than(graph, v, w):
				neighbors = graph.get_neighbors(v)
				for u in neighbors:
					if graph.is_directed_edge([u, w]) and less_than(graph, v, u):
						trias[v] += 1
						trias[w] += 1
						trias[u] += 1
		
		current += 1
		show_progress(current, total)

	# we counted everything twice
	for t in trias:
		trias[t] = int(trias[t] / 2)

	sys.stdout.write('\n')
	return trias


def clustering_coeff(graph, v_label, trias):
	v_idx = graph.get_index(v_label)
	deg_v = graph.degree(v_idx)
	if deg_v < 2:
		return float('nan')
	dv_c_2 = deg_v * (deg_v - 1) / 2.0
	return trias[v_idx] / dv_c_2


def create_labeled_landmarks(graph, naiive):
	verts = graph.get_verts()
	L = dict.fromkeys(verts)
	# initialize only once for better performance
	P = dict.fromkeys(verts, float('inf'))
	# for querying
	T = dict.fromkeys(verts, float('inf'))

	# for progess indicator
	total = len(verts)
	current = 0

	# create empty index
	for v in verts:
		L[v] = {}

	for v in verts:
		# bfs from v
		visited = []
		Q = deque()
		Q.appendleft(v)
		P[v] = 0

		# for querying
		if not naiive:
			for w in L[v]:
				T[w] = L[v][w]

		while Q:
			u = Q.pop()
			visited.append(u)

			if not naiive:
				# calculate shortest path for pruning
				sp = float('inf')
				for w in L[u]:
					path = L[u][w] + T[w]
					if path < sp:
						sp = path
			
			# naiive => never prune
			if naiive or sp > P[u]:
				for w in graph.get_neighbors(u):
					if P[w] == float('inf'):
						P[w] = P[u] + 1
						Q.appendleft(w)

		# reset
		for u in visited:
			# update L with results from BFS
			L[u][v] = P[u]
			P[u] = float('inf')
		if not naiive:
			for w in L[v]:
				T[w] = float('inf')
		
		current += 1
		show_progress(current, total)

	sys.stdout.write('\n')
	return L


def shortest_path_query(graph, v1_label, v2_label, L):
	sp = float('inf')

	idx1 = graph.get_index(v1_label)
	idx2 = graph.get_index(v2_label)

	for v in L[idx1]:
		if v in L[idx2]:
			path = L[idx1][v] + L[idx2][v]
			if path < sp:
				sp = path
				hop = v

	if sp == float('inf'):
		return [sp, 'none']
	
	return [sp, graph.get_label(hop)]


def export_json(file_name, content):
	with open(file_name, 'w') as f:
		json.dump(content, f, indent=4)


def import_json(file_name, content_type):
	with open(file_name, 'r') as f:    
		file_content = json.load(f)

	# convert json strings back to original ints (dict keys)
	# the indices are ordered so the vertices will have the same index as before
	converted_content = {}
	for c in file_content:
		c_int = int(c)
		if content_type == 'trias': 
			converted_content[c_int] = file_content[c]
		elif content_type == 'index':
			converted_content[c_int] = {}
			for cc in file_content[c]:
				converted_content[c_int][int(cc)] = file_content[c][cc]

	return converted_content


def time_diff_s(time_from):
	return time.time() - time_from


def main():
	ap = ArgumentParser()
	ap.add_argument('INPUT_FILE', help='the file that contains the graph')
	ap.add_argument('--pattern', metavar='PATTERN', default='\d+\\t\d+', help='specify a pattern to use when parsing the input file (default: \d+\\t\d+)')
	ap.add_argument('--split', metavar='PATTERN', default='\\t', help='specify a pattern to use when splitting the lines of the input file (default: \\t)')
	ap.add_argument('--indexfile', metavar='FILE', help='import labeled landmarks from JSON file')
	ap.add_argument('--saveindex', metavar='FILE', help='dump the labeled landmarks into a JSON file')
	ap.add_argument('--noprune', action='store_true', help='use naiive landmark labeling (no pruning)')
	ap.add_argument('-sp', nargs=2, metavar=('V1', 'V2'), action='append', help='calculate the shortest path between vertices V1 and V2')
	ap.add_argument('--triafile', metavar='FILE', help='import triangle counts from JSON file')
	ap.add_argument('--savetrias', metavar='FILE', help='dump the triangle counts into a JSON file')
	ap.add_argument('-cc', metavar='V', action='append', help='calculate the clustering coefficient of vertex V')
	args = ap.parse_args()

	# create graph
	print('reading file \'{}\'...'.format(args.INPUT_FILE))
	time_start = time.time()
	g = Graph.from_file(args.INPUT_FILE, args.pattern, args.split)
	time_end = time_diff_s(time_start)
	print('created adjacency list of graph with {} vertices [{:.3f}s]'.format(len(g.get_verts()), time_end))

	# create labeled landmarks
	if args.saveindex or args.sp:
		time_start = time.time()
		if args.indexfile:
			print('importing labeled landmarks from \'{}\'...'.format(args.indexfile))
			ll = import_json(args.indexfile, 'index')
		else:
			print('creating labeled landmarks...')
			ll = create_labeled_landmarks(g, args.noprune)
		time_end = time_diff_s(time_start)
		print('created labeled landmarks [{:.3f}s]'.format(time_end))

	# create triangle counts
	if args.savetrias or args.cc:
		time_start = time.time()
		if args.triafile:
			print('importing triangle counts from \'{}\'...'.format(args.triafile))
			trias = import_json(args.triafile, 'trias')
		else:
			print('counting triangles...')
			trias = count_triangles(g)
		time_end = time_diff_s(time_start)
		print('created triangle counts [{:.3f}s]'.format(time_end))

	# dump data into files
	if args.saveindex:
		print('exporting labeled landmarks to \'{}\'...'.format(args.saveindex))
		export_json(args.saveindex, ll)
	if args.savetrias:
		print('exporting triangle counts to \'{}\'...'.format(args.savetrias))
		export_json(args.savetrias, trias)

	if args.sp or args.cc:
		print('\n========================RESULTS========================')

	# execute all tasks
	if args.sp:
		for sp_req in args.sp:
			sp = shortest_path_query(g, sp_req[0], sp_req[1], ll)
			print('shortest path ({}) --> ({}) --> ({}): length {}'.format(sp_req[0], sp[1], sp_req[1], sp[0]))
	if args.cc:
		for cc_req in args.cc:
			cc = clustering_coeff(g, cc_req, trias)
			print('clustering coefficient of ({}): {}'.format(cc_req, cc))
			

if __name__ == '__main__':
	main()