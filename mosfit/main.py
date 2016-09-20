import argparse
import os

from mosfit.fitter import Fitter

from . import __version__


def main():
    """First, parse command line arguments.
    """

    parser = argparse.ArgumentParser(
        prog='MOSFiT',
        description='Fit astrophysical light curves using AstroCats data.')

    parser.add_argument(
        '--events',
        '-e',
        dest='events',
        default=[''],
        nargs='+',
        help=("List of event names to be fit, delimited by spaces. If an "
              "event name contains a space, enclose the event's name in "
              "double quote marks, e.g. \"SDSS-II SN 5944\"."))

    parser.add_argument(
        '--models',
        '-m',
        dest='models',
        default=['default'],
        nargs='+',
        help=("List of models to use to fit against the listed events. The "
              "model can either be a name of a model included with MOSFiT, or "
              "a path to a custom model JSON file generated by the user."))

    parser.add_argument(
        '--parameter-paths',
        '-P',
        dest='parameter_paths',
        default=[''],
        nargs='+',
        help=("Paths to parameter files corresponding to each model file; "
              "length of this list should be equal to the length of the list "
              "of models"))

    parser.add_argument(
        '--plot-points',
        dest='plot_points',
        default=100,
        help=("Set the number of plot points when producing light curves from "
              "models without fitting against any actual transient data."))

    parser.add_argument(
        '--max-time',
        dest='max_time',
        default=1000.,
        help=("Set the maximum time for model light curves to be plotted "
              "until."))

    parser.add_argument(
        '--band-list',
        dest='band_list',
        default=['V'],
        help=("List of bands to plot when plotting model light curves that "
              "are not being matched to actual transient data."))

    parser.add_argument(
        '--band-systems',
        dest='band_systems',
        default=[''],
        help=("List of photometric systems corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--band-instruments',
        dest='band_instruments',
        default=[''],
        help=("List of instruments corresponding to the bands listed "
              "in `--band-list`."))

    parser.add_argument(
        '--iterations',
        '-i',
        dest='iterations',
        type=int,
        default=1000,
        help=("Number of iterations to run emcee for, including burn-in and "
              "post-burn iterations."))

    parser.add_argument(
        '--num-walkers',
        '-N',
        dest='num_walkers',
        type=int,
        default=50,
        help=("Number of walkers to use in emcee, must be at least twice the "
              "total number of free parameters within the model."))

    parser.add_argument(
        '--num-temps',
        '-T',
        dest='num_temps',
        type=int,
        default=2,
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
        '--frack-step',
        '-f',
        dest='frack_step',
        type=int,
        default=20,
        help=("Perform `fracking` every this number of steps while in the "
              "burn-in phase of the fitting process."))

    parser.add_argument(
        '--post-burn',
        '-p',
        dest='post_burn',
        type=int,
        default=500,
        help=("Run emcee this many more iterations after the burn-in phase. "
              "The burn-in phase will thus be run for (i - p) iterations, "
              "where i is the total number of iterations set with `-i` and "
              "p is the value of this parameter."))

    parser.add_argument(
        '--travis',
        dest='travis',
        default=False,
        action='store_true',
        help=("Alters the printing of output messages such that a new line is "
              "generated with each message. Users are unlikely to need this "
              "parameter; it is included as Travis requires new lines to be "
              "produed to detected program output."))

    args = parser.parse_args()

    # Print our amazing ASCII logo.
    with open(os.path.join('mosfit', 'logo.txt'), 'r') as f:
        logo = f.read()
        width = len(logo.split('\n')[0])
        aligns = '{:^' + str(width) + '}'
        print(logo)
    print((aligns + '\n').format('### MOSFiT -- version {} ###'.format(
        __version__)))
    print(aligns.format('Authored by James Guillochon & Matt Nicholl'))
    print(aligns.format('Released under the MIT license'))
    print((aligns + '\n').format('https://github.com/guillochon/MOSFiT'))

    # Then, fit the listed events with the listed models.
    fitargs = {
        'events': args.events,
        'models': args.models,
        'plot_points': args.plot_points,
        'max_time': args.max_time,
        'band_list': args.band_list,
        'band_systems': args.band_systems,
        'band_instruments': args.band_instruments,
        'iterations': args.iterations,
        'num_walkers': args.num_walkers,
        'num_temps': args.num_temps,
        'parameter_paths': args.parameter_paths,
        'fracking': args.fracking,
        'frack_step': args.frack_step,
        'travis': args.travis,
        'post_burn': args.post_burn
    }
    Fitter().fit_events(**fitargs)


if __name__ == "__main__":
    main()