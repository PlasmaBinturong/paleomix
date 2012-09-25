#!/usr/bin/python
#
# Copyright (c) 2012 Mikkel Schubert <MSchubert@snm.ku.dk>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell 
# copies of the Software, and to permit persons to whom the Software is 
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
# SOFTWARE.
#
from __future__ import with_statement

import os
import textwrap

import pysam
import pypeline.common.fileutils as fileutils
import pypeline.common.formats.msa as msa

from pypeline.node import Node, MetaNode
from pypeline.common.formats.fasta import read_fasta
from pypeline.common.utilities import safe_coerce_to_tuple



class CollectSequencesNode(Node):
    def __init__(self, infiles, destination, sequences, dependencies):
        self._infiles     = dict(infiles)
        self._destination = str(destination)
        self._sequences   = list(sequences)
        self._outfiles    = []

        for sequence in self._sequences:
            self._outfiles.append(os.path.join(destination, sequence + ".fasta"))

        Node.__init__(self,
                      description  = "<CollectSequences: %i sequences from %i files -> '%s'>" \
                            % (len(sequences), len(self._infiles), destination),
                      input_files  = self._infiles.values(),
                      output_files = self._outfiles,
                      dependencies = dependencies)


    def _run(self, _config, temp):
        fastas = {}
        for (name, filename) in self._infiles.items():
            fastas[name] = dict(read_fasta(filename))
        fastas = list(sorted(fastas.items()))

        for sequence in self._sequences:
            filename = os.path.join(temp, sequence + ".fasta")

            with open(filename, "w") as fasta:
                for (name, sequences) in fastas:
                    fastaseq = textwrap.fill(sequences[sequence], 60)
                    assert fastaseq, (name, sequence)
                    fasta.write(">%s\n%s\n" % (name, fastaseq))


    def _teardown(self, _config, temp):
        for sequence in self._sequences:
            filename = sequence + ".fasta"
            infile   = os.path.join(temp, filename)
            outfile  = os.path.join(self._destination, filename)
        
            fileutils.move_file(infile, outfile)


class FilterSingletonsNode(Node):
    def __init__(self, input_file, output_file, filter_by, dependencies):
        self._input_file      = input_file
        self._output_file     = output_file
        self._filter_by       = dict(filter_by)

        Node.__init__(self,
                      description  = "<FilterSingleton: '%s' -> '%s'>" \
                            % (input_file, output_file),
                      input_files  = [input_file],
                      output_files = [output_file],
                      dependencies = dependencies)

    def _run(self, _config, temp):
        alignment = msa.read_msa(self._input_file)

        for to_filter in self._filter_by:
            groups = set(self._filter_by[to_filter])
            groups.add(to_filter)

            sequences = [alignment[group] for group in groups]
            sequence = list(alignment[to_filter])
            for (index, nts) in enumerate(zip(*sequences)):
                nt = sequence[index]
                if (nt not in "Nn-") and (nts.count(nt) == 1):
                    sequence[index] = 'n'

            alignment[to_filter] = "".join(sequence)

        temp_filename = fileutils.reroot_path(temp, self._output_file)
        msa.write_msa(alignment, temp_filename)
        fileutils.move_file(temp_filename, self._output_file)
       



class FilterSingletonsMetaNode(MetaNode):
    def __init__(self, input_files, destination, filter_by, dependencies = ()):
        subnodes = []
        filter_by = dict(filter_by)
        for (filename, node) in input_files.iteritems():
            output_filename = fileutils.reroot_path(destination, filename)
            subnodes.append(FilterSingletonsNode(input_file   = filename,
                                                 output_file  = output_filename,
                                                 filter_by    = filter_by,
                                                 dependencies = node))

        MetaNode.__init__(self,
                          description  = "<FilterSingleton: %i files -> '%s'>" \
                            % (len(subnodes), destination),
                          subnodes     = subnodes,
                          dependencies = dependencies)