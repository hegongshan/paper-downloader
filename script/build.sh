#!/bin/bash

help_msg() {
    echo "Usage:"
    echo
    echo "    -h, --help  Show this help message"
    echo "    -c, --cli   Build CLI"
    echo "    -g, --gui   Build GUI"
    echo "    -d, --dir   Save directory (default directory: .)"
}

build() {
    local mode="$1"
    local save_dir="$2"
    local pyinstaller_options="-F -y"
    if [ "${mode}" == "gui" ]; then
        pyinstaller_options+=" --add-data config:."
    fi
    echo "mode: \"${mode}\", dir: \"${save_dir}\", options: \"${pyinstaller_options}\""

    pip3 install -r requirements-${mode}.txt && \
        pip3 install pyinstaller && \
        pyinstaller ${pyinstaller_options} ${mode}.py && \
        rm -rf build ${mode}.spec && \
        cp dist/${mode} ${save_dir}/ && \
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
            echo "-d/--dir option requires a parameter."
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

for mode in ${modes[@]}; do
    build ${mode} ${dir}
done
