import os
import glob
import zipfile

import biothings.hub.dataload.uploader as uploader
import biothings.hub.dataload.storage as storage

from .gnomad_parser_genomes import load_data as load_data_genomes
from .gnomad_parser_exomes import load_data as load_data_exomes
from .mapping import exomes_mapping, genomes_mapping
from hub.dataload.uploader import SnpeffPostUpdateUploader

SRC_META = {
    "url" : "http://gnomad.broadinstitute.org",
    "license_url" : "http://gnomad.broadinstitute.org/terms",
    "license_url_short": "http://bit.ly/2I1cl1I",
    "license" : "ODbL"
}

class GnomadBaseUploader(uploader.IgnoreDuplicatedSourceUploader,SnpeffPostUpdateUploader):
    pass


class GnomadBaseHg19Uploader(GnomadBaseUploader):
    __metadata__ = {"mapper" : 'observed',
            "assembly" : "hg19",
            "src_meta" : SRC_META
            }


class GnomadBaseHg38Uploader(GnomadBaseUploader):
    __metadata__ = {"mapper" : 'observed',
            "assembly" : "hg38",
            "src_meta" : SRC_META
            }


class GnomadExomesBaseUploader(GnomadBaseUploader):

    def load_data(self,data_folder):
        files = glob.glob(os.path.join(data_folder,"exomes",self.__class__.GLOB_PATTERN))
        self.logger.info("papapap %s" % os.path.join(data_folder,"exomes",self.__class__.GLOB_PATTERN))
        if len(files) != 1:
            raise uploader.ResourceError("Expecting only one VCF file, got: %s" % files)
        input_file = files.pop()
        assert os.path.exists("%s%s" % (input_file,self.__class__.tbi_suffix)), "%s%s" % (input_file,self.__class__.tbi_suffix)
        self.logger.info("Load data from file '%s'" % input_file)
        res = load_data_exomes(input_file)
        return res

    @classmethod
    def get_mapping(klass):
        return exomes_mapping


class GnomadExomesHg19Uploader(GnomadBaseHg19Uploader,GnomadExomesBaseUploader):
    main_source = "gnomad"
    name = "gnomad_exomes_hg19"
    tbi_suffix = ".bgz.tbi"
    GLOB_PATTERN = "gnomad.exomes.*.vcf"


class GnomadExomesHg38Uploader(GnomadBaseHg38Uploader,GnomadExomesBaseUploader):
    main_source = "gnomad"
    name = "gnomad_exomes_hg38"
    tbi_suffix = ".gz.tbi"
    GLOB_PATTERN = "liftover_grch38/gnomad.exomes.*.vcf"


class GnomadGenomesBaseUploader(GnomadBaseUploader, uploader.ParallelizedSourceUploader):

    def jobs(self):
        # tuple(input_file,version), where version is either hg38 or hg19)
        files = [(e,) for e in glob.glob(os.path.join(self.data_folder, "genomes", self.__class__.GLOB_PATTERN))]
        assert len(files) >= 23, "Expecting at least 23 VCF files, got: %s" % files
        return files

    def load_data(self, input_file):
        self.logger.info("Load data from file '%s'" % input_file)
        res = load_data_genomes(input_file)
        return res

    @classmethod
    def get_mapping(klass):
        return genomes_mapping


class GnomadGenomesHg19Uploader(GnomadBaseHg19Uploader, GnomadGenomesBaseUploader):
    main_source = "gnomad"
    name = "gnomad_genomes_hg19"
    GLOB_PATTERN = "gnomad.genomes.*.vcf"


class GnomadGenomesHg38Uploader(GnomadBaseHg38Uploader, GnomadGenomesBaseUploader):
    main_source = "gnomad"
    name = "gnomad_genomes_hg38"
    GLOB_PATTERN = "liftover_grch38/gnomad.genomes.*.vcf"

