#!/usr/bin/env python2
#
# Script to build a Nix script to actually build a Steam runtime.
# Patched version of https://github.com/ValveSoftware/steam-runtime/blob/master/build-runtime.py

import os
import re
import sys
import urllib
import gzip
import cStringIO
import subprocess
from debian import deb822
import argparse

destdir="newpkg"
arches=["amd64", "i386"]

REPO="http://repo.steampowered.com/steamrt"
DIST="scout"
COMPONENT="main"

out = open("runtime-generated.nix", "w");
out.write("# This file is autogenerated! Do not edit it yourself, use update-runtime.py for regeneration.\n")
out.write("{ fetchurl }:\n")
out.write("\n")
out.write("{\n")

def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument("-b", "--beta", help="build beta runtime", action="store_true")
	parser.add_argument("-d", "--debug", help="build debug runtime", action="store_true")
	parser.add_argument("--symbols", help="include debugging symbols", action="store_true")
	parser.add_argument("--repo", help="source repository", default=REPO)
	return parser.parse_args()

def download_file(file_base, file_name, file_url):
	file_shortname = file_base + ".deb"
	sha256 = subprocess.check_output(["nix-prefetch-url", "--type", "sha256", "--name", file_shortname, file_url])
	out.write("    rec {\n")
	out.write("      name = \"%s\";\n" % file_name)
	out.write("      sha256 = \"%s\";\n" % sha256.strip())
	out.write("      url = \"%s\";\n" % file_url.replace(REPO, "mirror://steamrt", 1))
	out.write("      source = fetchurl {\n")
	out.write("        inherit url sha256;\n")
	out.write("        name = \"%s\";\n" % file_shortname)
	out.write("      };\n")
	out.write("    }\n")


def install_binaries (arch, binarylist):
	installset = binarylist.copy()

	#
	# Load the Packages file so we can find the location of each binary package
	#
	packages_url = "%s/dists/%s/%s/binary-%s/Packages" % (REPO, DIST, COMPONENT, arch)
	print("Downloading %s binaries from %s" % (arch, packages_url))
	for stanza in deb822.Packages.iter_paragraphs(urllib.urlopen(packages_url)):
		p = stanza['Package']
		if p in installset:
			print("DOWNLOADING BINARY: %s" % p)

			#
			# Download the package and install it
			#
			file_url="%s/%s" % (REPO,stanza['Filename'])
			download_file(p, os.path.splitext(os.path.basename(stanza['Filename']))[0], file_url)
			installset.remove(p)

	for p in installset:
		#
		# There was a binary package in the list to be installed that is not in the repo
		#
		e = "ERROR: Package %s not found in Packages file %s\n" % (p, packages_url)
		sys.stderr.write(e)



def install_symbols (arch, binarylist):
	#
	# Load the Packages file to find the location of each symbol package
	#
	packages_url = "%s/dists/%s/%s/debug/binary-%s/Packages" % (REPO, DIST, COMPONENT, arch)
	print("Downloading %s symbols from %s" % (arch, packages_url))
	for stanza in deb822.Packages.iter_paragraphs(urllib.urlopen(packages_url)):
		p = stanza['Package']
		m = re.match('([\w\-\.]+)\-dbgsym', p)
		if m and m.group(1) in binarylist:
			print("DOWNLOADING SYMBOLS: %s" % p)
			#
			# Download the package and install it
			#
			file_url="%s/%s" % (REPO,stanza['Filename'])
			download_file(p, os.path.splitext(os.path.basename(stanza['Filename']))[0], file_url)



args = parse_args()

REPO=args.repo

if args.beta:
	DIST="steam_beta"

if args.debug:
	COMPONENT = "debug"

# Process packages.txt to get the list of source and binary packages
source_pkgs = set()
binary_pkgs = set()

print ("Creating runtime-generated.nix")

pkgs_list = urllib.urlopen("https://raw.githubusercontent.com/ValveSoftware/steam-runtime/master/packages.txt").readlines()
for line in pkgs_list:
	if line[0] != '#':
		toks = line.split()
		if len(toks) > 1:
			source_pkgs.add(toks[0])
			binary_pkgs.update(toks[1:])

# remove development packages for end-user runtime
if not args.debug:
	binary_pkgs -= {x for x in binary_pkgs if re.search('-dbg$|-dev$|-multidev$',x)}

for arch in arches:
	out.write("  %s = [\n" % arch)
	install_binaries(arch, binary_pkgs)

	if args.symbols:
		install_symbols(arch, binary_pkgs)

	out.write("  ];\n");

out.write("}\n")

# vi: set noexpandtab:
