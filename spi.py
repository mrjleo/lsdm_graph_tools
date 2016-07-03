#! /usr/bin/python
# -*- coding: utf-8 -*-

import sys
import argparse
from graph import Graph


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument('INPUT_FILE')
	args = ap.parse_args()

	print('reading file \'{}\'...'.format(args.INPUT_FILE))
	g = Graph.from_file(args.INPUT_FILE)
	print('created graph with {} nodes'.format(g.vert_count()))
	print(g.graph)


if __name__ == '__main__':
	main()