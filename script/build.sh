#!/bin/bash

help_msg() {
    echo "Usage:"
    echo
    echo "    -h, --help     Show this help message"
    echo "    -c, --cli      Build CLI"
    echo "    -g, --gui      Build GUI"
    echo "    -d, --dir DIR  Save directory (default directory: .)"
}

build() {
    local mode="$1"
    local save_dir="$2"
    local app_name="apbdoav-${mode}"
    local pyinstaller_options="-F -y --name ${app_name}"
    if [ "${mode}" == "gui" ]; then
        pyinstaller_options+=" --add-data config:."
    fi
    echo "mode: \"${mode}\", dir: \"${save_dir}\", options: \"${pyinstaller_options}\""

    pip3 install -r requirements-${mode}.txt && \
        pip3 install pyinstaller && \
        pyinstaller ${pyinstaller_options} ${mode}.py && \
        rm -rf build ${app_name}.spec && \
        cp dist/${app_name} ${save_dir}/ && \
        rm -rf dist
}

modes=""
dir="."
while [[ $# -ne 0 ]]; do
    case "$1" in
    -h | --help)
        help_msg
        exit
        ;;
    -c | --cli)
        modes+=" cli"
        shift
        ;;
    -g | --gui)
        modes+=" gui"
        shift
        ;;
    -d | --dir)
        dir=$2
        if [ -z "${dir}" \
          -o "${dir}" = "-h" \
          -o "${dir}" = "--help" \
          -o "${dir}" = "-c" \
          -o "${dir}" = "--cli" \
          -o "${dir}" = "-g" \
          -o "${dir}" = "--gui" ]; then
            echo "Error: -d/--dir option requires a parameter."
            exit
        elif [ ! -e "${dir}" ]; then
            mkdir -p ${dir}
        fi
        shift 2
        ;;
    *)
        echo "unknown options: $1"
        exit
        ;;
    esac
done

if [ -z "${modes}" ]; then
  echo "Error: At least one of the -c/--cli or -g/--gui options need to be set."
else
    for mode in ${modes[@]}; do
        build ${mode} ${dir}
    done
fi
