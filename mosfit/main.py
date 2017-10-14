# -*- encoding: utf-8 -*-
"""The main function."""

import argparse
import codecs
import locale
import os
import shutil
import sys
import time
from operator import attrgetter
from unicodedata import normalize

import numpy as np

from mosfit import __author__, __contributors__, __version__
from mosfit.fitter import Fitter
from mosfit.printer import Printer
from mosfit.utils import get_mosfit_hash, is_master, open_atomic, speak


class SortingHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Sort argparse arguments by argument name."""

    def add_arguments(self, actions):
        """Add sorting action based on `option_strings`."""
        actions = sorted(actions, key=attrgetter('option_strings'))
        super(SortingHelpFormatter, self).add_arguments(actions)


def get_parser():
    """Retrieve MOSFiT's `argparse.ArgumentParser` object."""
    parser = argparse.ArgumentParser(
        prog='mosfit',
        description='Fit astrophysical transients.',
        formatter_class=SortingHelpFormatter)

    parser.add_argument(
        '--events',
        '-e',
        dest='events',
        default=[],
        nargs='+',
        help=("List of event names (or file names) to be fit, delimited by "
              "spaces. If an "
              "event name contains a space, enclose the event's name in "
              "double quote marks, e.g. \"SDSS-II SN 5944\". Files with "
              "`.json` extensions are presumed to be in Open Catalog "
              "format, whereas files with any other extension will be read "
              "as a list of event names."))

    parser.add_argument(
        '--models',
        '-m',
        dest='models',
        default=[],
        nargs='?',
        help=("List of models to use to fit against the listed events. The "
              "model can either be a name of a model included with MOSFiT, or "
              "a path to a custom model JSON file generated by the user."))

    parser.add_argument(
        '--parameter-paths',
        '-P',
        dest='parameter_paths',
        default=['parameters.json'],
        nargs='+',
        help=("Paths to parameter files corresponding to each model file; "
              "length of this list should be equal to the length of the list "
              "of models"))

    parser.add_argument(
        '--walker-paths',
        '-w',
        dest='walker_paths',
        default=[],
        nargs='+',
        help=("List of paths to Open Catalog format files with walkers from "
              "which to draw initial walker positions. Output data from "
              "MOSFiT can be loaded with this command. If some variables "
              "are not contained within the input file(s), they will "
              "instead be drawn randomly from the specified model priors."))

    parser.add_argument(
        '--max-time',
        dest='max_time',
        type=float,
        default=1000.,
        help=("Set the maximum time for model light curves to be plotted "
              "until."))

    parser.add_argument(
        '--limiting-magnitude',
        '-l',
        dest='limiting_magnitude',
        default=None,
        nargs='+',
        help=("Assumed limiting magnitude of a simulated survey. When "
              "enabled, model light curves will be randomly drawn and "
              "assigned error bars. If passed one argument, that number "
              "will be used as the limiting magnitude (default: `20`). "
              "If provided a second argument, that number will be used "
              "for observation-to-observation variance in the limit."))

    parser.add_argument(
        '--band-list',
        '--extra-bands',
        dest='band_list',
        default=[],
        nargs='+',
        help=("List of additional bands to plot when plotting model light "
              "curves that are not being matched to actual transient data."))

    parser.add_argument(
        '--band-systems',
        '--extra-systems',
        dest='band_systems',
        default=[],
        nargs='+',
        help=("List of photometric systems corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--band-instruments',
        '--extra-instruments',
        dest='band_instruments',
        default=[],
        nargs='+',
        help=("List of instruments corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--band-bandsets',
        '--extra-bandsets',
        dest='band_bandsets',
        default=[],
        nargs='+',
        help=("List of bandsets corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--band-sampling-points',
        dest='band_sampling_points',
        type=int,
        default=17,
        help=("Number of wavelengths to sample in each band when modeling "
              "photometry."))

    parser.add_argument(
        '--exclude-bands',
        dest='exclude_bands',
        default=[],
        nargs='+',
        help=("List of bands to exclude in fitting."))

    parser.add_argument(
        '--exclude-instruments',
        dest='exclude_instruments',
        default=[],
        nargs='+',
        help=("List of instruments to exclude in fitting corresponding to "
              "the bands listed in `--exclude-bands`."))

    parser.add_argument(
        '--exclude-systems',
        dest='exclude_systems',
        default=[],
        nargs='+',
        help=("List of systems to exclude in fitting corresponding to "
              "the bands listed in `--exclude-bands`."))

    parser.add_argument(
        '--exclude-sources',
        dest='exclude_sources',
        default=[],
        nargs='+',
        help=("List of references to exclude data from when fitting. These "
              "are specified using the source ID number that is shown on the "
              "Open Astronomy Catalog page for each transient. "))

    parser.add_argument(
        '--fix-parameters',
        '-F',
        dest='user_fixed_parameters',
        default=[],
        nargs='+',
        help=("Pairs of parameter names and values to fix for the current "
              "fit. Example: `-F kappa 1.0 vejecta 1.0e4` would fix the "
              "`kappa` and `vejecta` parameters to those values. If the "
              "second value is recognized to be an existing key, the whole "
              "list will be assumed to just be a list of keys and the "
              "default values specified in the model JSON files will be "
              "used. If the name is a parameter class (e.g. `covariance`), "
              "all variables of that class will be fixed."))

    parser.add_argument(
        '--iterations',
        '-i',
        dest='iterations',
        type=int,
        const=0,
        default=-1,
        nargs='?',
        help=("Number of iterations to run emcee for, including burn-in and "
              "post-burn iterations. Setting this option to `0` (or "
              "providing no argument) will only draw walker positions "
              "and immediately exit."))

    parser.add_argument(
        '--smooth-times',
        '--plot-points',
        '-S',
        dest='smooth_times',
        type=int,
        const=0,
        default=20,
        nargs='?',
        action='store',
        help=("Add this many more fictitious observations between the first "
              "and last observed times. Setting this value to `0` (or "
              "providing no argument) will "
              "guarantee that all observed bands/instrument/system "
              "combinations have a point at all observed epochs, but no other "
              "times. A negative "
              "value will only yield model predictions at the observations "
              "but at no other times (faster but sparser light curves)."))

    parser.add_argument(
        '--extrapolate-time',
        '-E',
        dest='extrapolate_time',
        type=float,
        default=0.0,
        nargs='*',
        help=(
            "Extend model light curves this many days before/after "
            "first/last observation. Can be a list of two elements, in which "
            "case the first element is the amount of time before the first "
            "observation to extrapolate, and the second element is the amount "
            "of time before the last observation to extrapolate. Value is set "
            "to `0.0` days if option not set, `100.0` days "
            "by default if no arguments are given."))

    parser.add_argument(
        '--limit-fitting-mjds',
        '-L',
        dest='limit_fitting_mjds',
        type=float,
        default=False,
        nargs=2,
        help=(
            "Only include observations with MJDs within the specified range, "
            "e.g. `-L 54123 54234` will exclude observations outside this "
            "range. If specified without an argument, any upper limit "
            "observations before the last upper limit before the first "
            "detection in a given band will not be included in the fitting."))

    parser.add_argument(
        '--suffix',
        '-s',
        dest='suffix',
        default='',
        help=("Append custom string to output file name to prevent overwrite"))

    parser.add_argument(
        '--num-walkers',
        '-N',
        dest='num_walkers',
        type=int,
        default=None,
        help=("Number of walkers to use in emcee. When fitting, this must be "
              "set to at least twice the "
              "total number of free parameters within the model, not "
              "setting this parameter will set it to this minimum."))

    parser.add_argument(
        '--num-temps',
        '-T',
        dest='num_temps',
        type=int,
        default=1,
        help=("Number of temperatures to use in the parallel-tempered emcee "
              "sampler. `-T 1` is equivalent to the standard "
              "EnsembleSampler."))

    parser.add_argument(
        '--no-fracking',
        dest='fracking',
        default=True,
        action='store_false',
        help=("Setting this flag will skip the `fracking` step of the "
              "optimization process."))

    parser.add_argument(
        '--no-write',
        dest='write',
        default=True,
        action='store_false',
        help=("Do not write any results to disk."))

    parser.add_argument(
        '--quiet',
        dest='quiet',
        default=False,
        action='store_true',
        help=("Print minimal output upon execution. Don't display our "
              "amazing logo :-("))

    parser.add_argument(
        '--cuda',
        dest='cuda',
        default=False,
        action='store_true',
        help=("Enable CUDA for MOSFiT routines. Requires the `scikit-cuda` "
              "package (and its dependencies) to be installed."))

    parser.add_argument(
        '--no-copy-at-launch',
        dest='copy',
        default=True,
        action='store_false',
        help=("Setting this flag will prevent MOSFiT from copying the user "
              "file hierarchy (models/modules/jupyter) to the current working "
              "directory before fitting."))

    parser.add_argument(
        '--force-copy-at-launch',
        dest='force_copy',
        default=False,
        action='store_true',
        help=("Setting this flag will force MOSFiT to overwrite the user "
              "file hierarchy (models/modules/jupyter) to the current working "
              "directory. User will be prompted before being allowed to run "
              "with this flag."))

    parser.add_argument(
        '--offline',
        dest='offline',
        default=False,
        action='store_true',
        help=("MOSFiT will only use cached data and will not attempt to use "
              "any online resources."))

    parser.add_argument(
        '--frack-step',
        '-f',
        dest='frack_step',
        type=int,
        default=50,
        help=("Perform `fracking` every this number of steps while in the "
              "burn-in phase of the fitting process."))

    parser.add_argument(
        '--burn',
        '-b',
        dest='burn',
        type=int,
        help=("Burn in the chains for this many iterations. During burn-in, "
              "global optimization (\"fracking\"), replacement, and a "
              "Gibbs variant of emcee are used to speed convergence. "
              "However, as none of these methods preserve detailed "
              "balance, the posteriors obtained during the burn-in phase "
              "are very approximate. No convergence information will be "
              "displayed during burn-in."))

    parser.add_argument(
        '--post-burn',
        '-p',
        dest='post_burn',
        type=int,
        help=("Run emcee this many more iterations after the burn-in phase. "
              "The burn-in phase will thus be run for (i - p) iterations, "
              "where i is the total number of iterations set with `-i` and "
              "p is the value of this parameter."))

    parser.add_argument(
        '--upload',
        '-u',
        dest='upload',
        default=False,
        action='store_true',
        help=("Upload results of MOSFiT to appropriate Open Catalog. If "
              "MOSFiT is only supplied with `-u` and no other arguments, it "
              "will upload the results of the latest run."))

    parser.add_argument(
        '--run-until-converged',
        '-R',
        dest='run_until_converged',
        type=float,
        default=None,
        const=1.1,
        nargs='?',
        help=("Run each model until the autocorrelation time is measured "
              "accurately and chain has burned in for the specified number "
              "of autocorrelation times [Default: 10.0]. This will run "
              "beyond the specified number of iterations, and is recommended "
              "when the `--upload/-u` flag is set."))

    parser.add_argument(
        '--run-until-uncorrelated',
        '-U',
        dest='run_until_uncorrelated',
        type=int,
        default=None,
        const=5,
        nargs='?',
        help=("Run each model until the autocorrelation time is measured "
              "accurately and chain has burned in for the specified number "
              "of autocorrelation times [Default: 10.0]. This will run "
              "beyond the specified number of iterations, and is recommended "
              "when the `--upload/-u` flag is set."))

    parser.add_argument(
        '--maximum-walltime',
        '-W',
        dest='maximum_walltime',
        type=float,
        default=False,
        help=("Total execution time (in seconds) constrained to be no "
              "greater than this value."))

    parser.add_argument(
        '--maximum-memory',
        '-M',
        dest='maximum_memory',
        type=float,
        default=np.inf,
        help=("Maximum memory MOSFiT is allowed to use, in megabytes. The "
              "memory use is roughly estimated, so it is best to set this "
              "number at least 1 GB below your system\'s actual memory limit "
              "per CPU."))

    parser.add_argument(
        '--draw-above-likelihood',
        '-d',
        dest='draw_above_likelihood',
        type=float,
        default=False,
        const=True,
        nargs='?',
        help=("When randomly drawing walkers initially, do not accept a draw "
              "unless a likelihood value is greater than this value. By "
              "default, any score greater than the likelihood floor will be "
              "retained."))

    parser.add_argument(
        '--gibbs',
        '-g',
        dest='gibbs',
        default=False,
        action='store_true',
        help=("Using a Gibbs-sampling variant of emcee. This is not proven "
              "to preserve detailed balance, however it has much faster "
              "convergence than the vanilla emcee stretch-move. Use with "
              "caution."))

    parser.add_argument(
        '--save-full-chain',
        '-c',
        dest='save_full_chain',
        default=False,
        action='store_true',
        help=("Save the full chain for each model fit."))

    parser.add_argument(
        '--print-trees',
        dest='print_trees',
        default=False,
        action='store_true',
        help=("Print the full dependency trees of each model."))

    parser.add_argument(
        '--set-upload-token',
        dest='set_upload_token',
        const=True,
        default=False,
        nargs='?',
        help=("Set the upload token. If given an argument, expects a 64-"
              "character token. If given no argument, MOSFiT will prompt "
              "the user to provide a token."))

    parser.add_argument(
        '--ignore-upload-quality',
        dest='check_upload_quality',
        default=True,
        action='store_false',
        help=("Ignore all quality checks when uploading fits."))

    parser.add_argument(
        '--test',
        dest='test',
        default=False,
        action='store_true',
        help=("Alters the printing of output messages such that a new line is "
              "generated with each message. Users are unlikely to need this "
              "parameter; it is included as Travis requires new lines to be "
              "produed to detected program output."))

    parser.add_argument(
        '--variance-for-each',
        dest='variance_for_each',
        default=[],
        nargs='+',
        help=("Create a separate `Variance` for each type of observation "
              "specified. Currently `band` is the only valid option, with "
              "a trailing numeric value indicating the maximum fractional "
              "difference in wavelength for two bands to be grouped."))

    parser.add_argument(
        '--speak',
        dest='speak',
        const='en',
        default=False,
        nargs='?',
        help=("Speak."))

    parser.add_argument(
        '--version',
        dest='version',
        default=False,
        action='store_true',
        help=("Print code version info."))

    parser.add_argument(
        '--language',
        dest='language',
        type=str,
        const='select',
        default='en',
        nargs='?',
        help=("Language for output text."))

    parser.add_argument(
        '--extra-outputs',
        '-x',
        dest='extra_outputs',
        default=[],
        nargs='+',
        help=("Extra keys to save alongside the default model outputs."))

    parser.add_argument(
        '--catalogs',
        '-C',
        dest='catalogs',
        default=[],
        nargs='+',
        help=("Restrict data acquisition to the listed catalogs."))

    parser.add_argument(
        '--open-in-browser',
        '-O',
        dest='open_in_browser',
        default=False,
        action='store_true',
        help=("Open the events listed with `-e` in the user's web "
              "browser one at a time."))

    parser.add_argument(
        '--exit-on-prompt',
        dest='exit_on_prompt',
        default=False,
        action='store_true',
        help=("Exit immediately if any user prompts are encountered "
              "(useful for batch jobs)."))

    parser.add_argument(
        '--download-recommended-data',
        dest='download_recommended_data',
        default=False,
        action='store_true',
        help=("Downloads any recommended data from the Open Catalogs if not "
              "provided by the user (without prompting)."))

    parser.add_argument(
        '--local-data-only',
        dest='local_data_only',
        default=False,
        action='store_true',
        help=("Will not attempt to acquire any data from the Open Catalogs "
              "(even from cache), using only data provided locally by the "
              "user."))

    return parser


def main():
    """Run MOSFiT."""
    parser = get_parser()

    args = parser.parse_args()

    if args.version:
        print('MOSFiT v{}'.format(__version__))
        return

    dir_path = os.path.dirname(os.path.realpath(__file__))

    if args.speak:
        speak('Mosfit', args.speak)

    if args.language == 'en':
        loc = locale.getlocale()
        if loc[0]:
            args.language = loc[0].split('_')[0]

    if args.language != 'en':
        try:
            from googletrans.constants import LANGUAGES
        except Exception:
            raise RuntimeError(
                '`--language` requires `googletrans` package, '
                'install with `pip install googletrans`.')

        if args.language == 'select' or args.language not in LANGUAGES:
            tprt = Printer(wrap_length=100, quiet=args.quiet, language='en',
                           exit_on_prompt=args.exit_on_prompt)
            languages = list(
                sorted([LANGUAGES[x].title().replace('_', ' ') +
                        ' (' + x + ')' for x in LANGUAGES]))
            sel = tprt.prompt(
                'Select a language:', kind='select', options=languages,
                message=False)
            args.language = sel.split('(')[-1].strip(')')

    prt = Printer(wrap_length=100, quiet=args.quiet, language=args.language,
                  exit_on_prompt=args.exit_on_prompt)

    args.start_time = time.time()

    if args.limiting_magnitude == []:
        args.limiting_magnitude = 20.0

    args.return_fits = False

    if (isinstance(args.extrapolate_time, list) and
            len(args.extrapolate_time) == 0):
        args.extrapolate_time = 100.0

    if len(args.band_list) and args.smooth_times == -1:
        prt.message('enabling_s')
        args.smooth_times = 0

    changed_iterations = False
    if args.iterations == -1:
        if len(args.events) == 0:
            changed_iterations = True
            args.iterations = 0
        else:
            args.iterations = 5000

    if args.burn is None and args.post_burn is None:
        args.burn = int(np.floor(args.iterations / 2))

    if args.frack_step == 0:
        args.fracking = False

    if (args.run_until_uncorrelated is not None and
            args.run_until_converged is not None):
        raise ValueError(
            '`-R` and `-U` options are incompatible, please use one or the '
            'other.')
    elif args.run_until_uncorrelated is not None:
        args.convergence_type = 'acor'
        args.convergence_criteria = args.run_until_uncorrelated
    elif args.run_until_converged is not None:
        args.convergence_type = 'psrf'
        args.convergence_criteria = args.run_until_converged

    if is_master():
        # Get hash of ourselves
        mosfit_hash = get_mosfit_hash()

        # Print our amazing ASCII logo.
        if not args.quiet:
            with codecs.open(os.path.join(dir_path, 'logo.txt'),
                             'r', 'utf-8') as f:
                logo = f.read()
                firstline = logo.split('\n')[0]
                # if isinstance(firstline, bytes):
                #     firstline = firstline.decode('utf-8')
                width = len(normalize('NFC', firstline))
            prt.prt(logo, colorify=True)
            prt.message(
                'byline', reps=[
                    __version__, mosfit_hash, __author__, __contributors__],
                center=True, colorify=True, width=width, wrapped=False)

        # Get/set upload token
        upload_token = ''
        get_token_from_user = False
        if args.set_upload_token:
            if args.set_upload_token is not True:
                upload_token = args.set_upload_token
            get_token_from_user = True

        upload_token_path = os.path.join(dir_path, 'cache', 'dropbox.token')

        # Perform a few checks on upload before running (to keep size
        # manageable)
        if args.upload and not args.test and args.smooth_times > 100:
            response = prt.prompt('ul_warning_smooth')
            if response:
                args.upload = False
            else:
                sys.exit()

        if (args.upload and not args.test and
                args.num_walkers is not None and args.num_walkers < 100):
            response = prt.prompt('ul_warning_few_walkers')
            if response:
                args.upload = False
            else:
                sys.exit()

        if (args.upload and not args.test and args.num_walkers and
                args.num_walkers * args.num_temps > 500):
            response = prt.prompt('ul_warning_too_many_walkers')
            if response:
                args.upload = False
            else:
                sys.exit()

        if args.upload:
            if not os.path.isfile(upload_token_path):
                get_token_from_user = True
            else:
                with open(upload_token_path, 'r') as f:
                    upload_token = f.read().splitlines()
                    if len(upload_token) != 1:
                        get_token_from_user = True
                    elif len(upload_token[0]) != 64:
                        get_token_from_user = True
                    else:
                        upload_token = upload_token[0]

        if get_token_from_user:
            if args.test:
                upload_token = ('1234567890abcdefghijklmnopqrstuvwxyz'
                                '1234567890abcdefghijklmnopqr')
            while len(upload_token) != 64:
                prt.message('no_ul_token', ['https://sne.space/mosfit/'],
                            wrapped=True)
                upload_token = prt.prompt('paste_token', kind='string')
                if len(upload_token) != 64:
                    prt.prt(
                        'Error: Token must be exactly 64 characters in '
                        'length.', wrapped=True)
                    continue
                break
            with open_atomic(upload_token_path, 'w') as f:
                f.write(upload_token)

        if args.upload:
            prt.prt(
                "Upload flag set, will upload results after completion.",
                wrapped=True)
            prt.prt("Dropbox token: " + upload_token, wrapped=True)

        args.upload_token = upload_token

        if changed_iterations:
            prt.message('iterations_0', wrapped=True)

        # Create the user directory structure, if it doesn't already exist.
        if args.copy:
            prt.message('copying')
            fc = False
            if args.force_copy:
                fc = prt.prompt('force_copy')
            if not os.path.exists('jupyter'):
                os.mkdir(os.path.join('jupyter'))
            if not os.path.isfile(os.path.join('jupyter',
                                               'mosfit.ipynb')) or fc:
                shutil.copy(
                    os.path.join(dir_path, 'jupyter', 'mosfit.ipynb'),
                    os.path.join(os.getcwd(), 'jupyter', 'mosfit.ipynb'))

            if not os.path.exists('modules'):
                os.mkdir(os.path.join('modules'))
            module_dirs = next(os.walk(os.path.join(dir_path, 'modules')))[1]
            for mdir in module_dirs:
                if mdir.startswith('__'):
                    continue
                full_mdir = os.path.join(dir_path, 'modules', mdir)
                copy_path = os.path.join(full_mdir, '.copy')
                to_copy = []
                if os.path.isfile(copy_path):
                    to_copy = list(filter(None, open(
                        copy_path, 'r').read().split()))

                mdir_path = os.path.join('modules', mdir)
                if not os.path.exists(mdir_path):
                    os.mkdir(mdir_path)
                for tc in to_copy:
                    tc_path = os.path.join(full_mdir, tc)
                    if os.path.isfile(tc_path):
                        shutil.copy(tc_path, os.path.join(mdir_path, tc))
                    elif os.path.isdir(tc_path) and not os.path.exists(
                            os.path.join(mdir_path, tc)):
                        os.mkdir(os.path.join(mdir_path, tc))
                readme_path = os.path.join(mdir_path, 'README')
                if not os.path.exists(readme_path):
                    txt = prt.message('readme-modules', [
                        os.path.join(dir_path, 'modules', 'mdir'),
                        os.path.join(dir_path, 'modules')], prt=False)
                    open(readme_path, 'w').write(txt)

            if not os.path.exists('models'):
                os.mkdir(os.path.join('models'))
            model_dirs = next(os.walk(os.path.join(dir_path, 'models')))[1]
            for mdir in model_dirs:
                if mdir.startswith('__'):
                    continue
                mdir_path = os.path.join('models', mdir)
                if not os.path.exists(mdir_path):
                    os.mkdir(mdir_path)
                model_files = next(
                    os.walk(os.path.join(dir_path, 'models', mdir)))[2]
                readme_path = os.path.join(mdir_path, 'README')
                if not os.path.exists(readme_path):
                    txt = prt.message('readme-models', [
                        os.path.join(dir_path, 'models', mdir),
                        os.path.join(dir_path, 'models')], prt=False)
                    with open(readme_path, 'w') as f:
                        f.write(txt)
                for mfil in model_files:
                    if 'parameters.json' not in mfil:
                        continue
                    fil_path = os.path.join(mdir_path, mfil)
                    if os.path.isfile(fil_path) and not fc:
                        continue
                    shutil.copy(
                        os.path.join(dir_path, 'models', mdir, mfil),
                        os.path.join(fil_path))

    # Then, fit the listed events with the listed models.
    fitargs = vars(args)
    Fitter(**fitargs).fit_events(**fitargs)


if __name__ == "__main__":
    main()
