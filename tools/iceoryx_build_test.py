#!/usr/bin/env python
import argparse
import subprocess
import shutil
import os

try:
  from pathlib import Path
except ImportError:
  from pathlib2 import Path

do_test = False
test_filter = ''


def main():

    # set build variables
    cmake_args = ""
    build_flags = [('','')]
    repo_dir = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'],
                                stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')

    build_dir = os.path.normpath(os.path.join(repo_dir, "build"))
    print(" [i] build directory:", build_dir)
    iceoryx_prefix = os.path.normpath(os.path.join(build_dir, "install", "prefix"))
    bool_build_iceoryx = True

    # complete list of examples to build, should be the folder name where the example is stored
    # elements are removed based on the buildflags
    examples = ['icedelivery', 'iceperf', 'benchmark_optional_and_expected',
                'singleprocess']
    components = ['posh', 'utils']

    # parse cmdline arguments
    parser = argparse.ArgumentParser(
        description='Iceoryx build and test script.')
    parser.add_argument('type', nargs='?', default='Debug', choices=['Debug', 'Release', 'RelWithDebInfo', 'MinSizeRel'],
                        help='Build type for cmake, you can choose between Debug, Release, RelWithDebInfo or MinSizeRel mode (default: Debug).')
    parser.add_argument('--jobs', '-j', nargs='?', const='4', default='4',
                        help='Number of parallel build jobs (default: 4)')
    parser.add_argument('--build_dir', '-b', nargs='?', const='', default=build_dir,
                        help='Specify a non-default build directory')
    parser.add_argument('--coverage', '-c', nargs='?', const='', default='', choices=['unit', 'integration', 'all'],
                        help='Do a Coverage scan. Argument is on which testlevel to create the coverage report')
    parser.add_argument('--clean', action='store_true',
                        help='Delete build folder for clean build')
    # parser.add_argument('--examples', action='store_true',
    #                     help='Build iceoryx examples')
    # parser.add_argument('--all', action='store_true',
    #                     help='Build & Run all tests and examples with all flags enabled')
    parser.add_argument('--strict', nargs='?', const='-DBUILD_STRICT=ON', default='-DBUILD_STRICT=OFF',
                        help='Threat compile warnings as errors (default off)')
    # parser.add_argument('--introspection', nargs='?', const='-Dintrospection=ON', default='-Dintrospection=OFF',
    #                     help='Build the iceoryx introspection (default on)')
    # parser.add_argument('--dds_gateway', nargs='?', const='-Ddds_gateway=ON', default='-Ddds_gateway=OFF',
    #                     help='Build the iceoryx dds gateway (default off)')
    # parser.add_argument('--c_binding', nargs='?', const='-Dbinding_c=ON', default='-Dbinding_c=OFF',
    #                     help='Build the iceoryx C Binding (default off)')
    # parser.add_argument('--one_to_many', nargs='?', const='-DONE_TO_MANY_ONLY=ON', default='-DONE_TO_MANY_ONLY=OFF',
    #                     help='Restricts to 1:n communication (default off)')
    # # parser.add_argument('--json', nargs='?', const='-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', default='-DCMAKE_EXPORT_COMPILE_COMMANDS=OFF',
    #                     help='Compile Commands JSON is generated (default on)')
    parser.add_argument('--test', nargs='?', action=SetTestFilter,
                        help='Build & Execute tests. Parameter is a filter statement be provided. For example to run only timing tests use "--test *.TimingTest_*". Default is to run all tests.')
    parser.add_argument('--build', nargs='*',
                        help='Build iceoryx with parameters.')
    args = parser.parse_args()

    # set variables from cmdline parser
    numjobs = '-j ' + args.jobs
    build_dir = args.build_dir
    global do_test
    global test_filter

    if args.coverage:
        args.build = 'all'
        args.examples = False

    if args.build is not None:
        if 'json' or 'all' in args.build:
            build_flags.append(('json', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'))
            print(" [i] build_flags: ", build_flags)
        if 'introspection' or 'all' in args.build:
            args.introspection = '-Dintrospection=ON'
        if 'one_to_many' or 'all' in args.build:
            args.one_to_many = '-DONE_TO_MANY_ONLY=ON'
        if 'c_binding' or 'all' in args.build:
            args.c_binding = '-Dbinding_c=ON'
            components.append('binding_c')
            examples.extend(['icedelivery_on_c', 'icecallback_on_c'])
        if 'dds_gateway' or 'all' in args.build:
            args.dds_gateway = '-Ddds_gateway=ON'
            components.append('dds_gateway')
        if 'test' or 'all' in args.build:
            args.test = '-Dtest=ON'
        if 'examples' or 'all' in args.build:
            args.test = '-Ddds_gateway=ON'
            args.examples = True
    else:
        print(" [i] unknown build flag", args.build)

    if args.clean & Path(build_dir).exists():
        print(" [i] Cleaning build directory")
        shutil.rmtree(build_dir, ignore_errors=True)

    # cmake argument list for build & test
    cmake_args = [numjobs, build_dir, repo_dir,
                  iceoryx_prefix, args, build_flags]

    if do_test:
        for component in components:
            if not Path(os.path.normpath(os.path.join(build_dir, component, "test"))).exists():
                bool_build_iceoryx = True
            else:
                bool_build_iceoryx = False
        args.test = test_filter

    if bool_build_iceoryx:
        build_iceoryx(cmake_args)

    if args.coverage:
        coverage_call = subprocess.run(
            ['./tools/gcov/lcov_generate.sh', repo_dir, 'initial'], check=True, cwd=repo_dir)

    if args.examples:
        build_examples(cmake_args, examples)

    if do_test:
        run_tests(cmake_args, components)

    if args.coverage:
        coverage_call = subprocess.run(
            ['./tools/gcov/lcov_generate.sh', repo_dir, 'capture'], check=True, cwd=repo_dir)
        coverage_call = subprocess.run(
            ['./tools/gcov/lcov_generate.sh', repo_dir, 'combine'], check=True, cwd=repo_dir)
        coverage_call = subprocess.run(
            ['./tools/gcov/lcov_generate.sh', repo_dir, 'remove'], check=True, cwd=repo_dir)
        coverage_call = subprocess.run(
            ['./tools/gcov/lcov_generate.sh', repo_dir, 'genhtml'], check=True, cwd=repo_dir)


def build_iceoryx(cmake_args):
    test = '-Dtest=OFF'
    roudi_env = '-Droudi_environment=OFF'
    coverage = '-Dcoverage=OFF'

    if not Path(cmake_args[1]).exists():
        Path(cmake_args[1]).mkdir()

    os.chdir(cmake_args[1])

    print(" Build iceoryx dir:", cmake_args[1])

    if cmake_args[4].coverage:
        coverage = '-Dcoverage=ON'

    global do_test
    if do_test:
        test = '-Dtest=ON'
        roudi_env = '-Droudi_environment=ON'

    cmake_dir = os.path.normpath(os.path.join("..", "iceoryx_meta"))

    print(" [i] Build iceoryx")
    cmake_call = subprocess.run(
        ['cmake', '-DCMAKE_BUILD_TYPE=' + cmake_args[4].type, '-DCMAKE_PREFIX_PATH=' + cmake_args[3], '-DCMAKE_INSTALL_PREFIX=' + cmake_args[3], cmake_args[4].c_binding, cmake_args[4].strict, test, roudi_env,
         cmake_args[5].json, cmake_args[4].introspection, cmake_args[4].dds_gateway, cmake_args[4].one_to_many, coverage, cmake_dir], check=True)
    make_call = subprocess.run(
        ['cmake', '--build', '.', '--target', 'install', cmake_args[0]], check=True)


def build_examples(cmake_args, examples):

    os.chdir(cmake_args[1])
    Path('iceoryx_examples').mkdir(exist_ok=True)

    print(" [i] Build iceoryx examples")

    os.chdir('iceoryx_examples')

    for example in examples:
        Path(example).mkdir(exist_ok=True)

        os.chdir(example)
        print(" [i] Build iceoryx examples")
        cmake_call = subprocess.run(
            ['cmake', '-DCMAKE_PREFIX_PATH=' + cmake_args[3], '-DCMAKE_INSTALL_PREFIX=' + cmake_args[3], cmake_args[2] + '/iceoryx_examples/' + example], check=True)
        make_call = subprocess.run(
            ['cmake', '--build', '.', '--target', 'install', cmake_args[0]], check=True)


def run_tests(cmake_args, components):
    print(">>>>>> Running Ice0ryx Tests <<<<<<")
    os.chdir(cmake_args[1])

    test_results_dir = 'testresults'
    test_levels = ['_moduletests', '_integrationtests', '_componenttests']

    if cmake_args[4].coverage == 'unit':
        test_levels.clear()
        test_levels = ['_moduletests']
    elif cmake_args[4].coverage == 'integration':
        test_levels.clear()
        test_levels = ['_integrationtests']

    if not Path(test_results_dir).exists():
        Path(test_results_dir).mkdir(exist_ok=True)

    for component in components:
        print("######################## executing tests for " +
              component + " ########################") 

        for test_level in test_levels:
            output_file = os.path.normpath(os.path.join(cmake_args[1], test_results_dir, component, test_level, "_results.xml"))
            
            if os.name == 'posix':
                testfile = Path(os.path.normpath(os.path.join(cmake_args[1], component, "test", (component + test_level))))
                print("testfile: ", testfile)
            
            elif os.name == 'nt':
                testfile = Path(os.path.normpath(os.path.join(cmake_args[1], component, "test", "Debug", (component + test_level))))
                print("testfile: ", testfile)
                
            test_call = subprocess.run([testfile, '--gtest_filter=' + cmake_args[4].test,
                                        '--gtest_output=xml:' + output_file], check=True)                    

class SetTestFilter(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        global do_test
        do_test = True

        global test_filter
        if values is not None:
            # take argument as gtest filter
            test_filter = values
        else:
            #Execute all tests
            test_filter = '*'

if __name__ == "__main__":
    main()
