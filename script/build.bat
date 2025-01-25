@echo off

set modes=
set dir=

:parse_args
if "%1" == "" (
    goto end
) else if "%1" ==  "-h" (
    call :help_msg
    exit /b
) else if "%1" ==  "--help" (
    call :help_msg
    exit /b
) else if "%1" == "-c" (
    set "modes=%modes% cli"
    shift
) else if "%1" == "--cli" (
    set "modes=%modes% cli"
    shift
) else if "%1" == "-g" (
    set "modes=%modes% gui"
    shift
) else if "%1" == "--gui" (
    set "modes=%modes% gui"
    shift
) else if "%1" == "-d" (
    if "%2" == "" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "-h" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "--help" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "-c" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "--cli" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "-g" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "--gui" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else (
        set "dir=%2"
        shift
        shift
    )
) else if "%1" == "--dir" (
    if "%2" == "" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "-h" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "--help" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "-c" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "--cli" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "-g" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else if "%2" == "--gui" (
        echo Error: %1 option requires a parameter.
        exit /b
    ) else (
        set "dir=%2"
        shift
        shift
    )
) else (
    echo Invalid option: %1
    exit /b
)
goto parse_args

:end
if "%modes%" == "" (
    echo Error: At least one of the -c/--cli or -g/--gui options need to be set.
) else (
    for %%m in (%modes%) do (
        call :build %%m %dir%
    )
)
exit /b

:help_msg
echo Usage:
echo.
echo     -h, --help     Show this help message
echo     -c, --cli      Build CLI
echo     -g, --gui      Build GUI
echo     -d, --dir DIR  Save directory (default directory: .)
exit /b

:build
set "m=%1"

if "%2" == "" (
    set "save_dir=."
) else (
    set "save_dir=%2"
)
if not exist "%save_dir%" (
    echo Create directory "%save_dir%".
    mkdir %save_dir%
)

set "pyinstaller_options=-F -y"
if "%m%" == "gui" (
    set "pyinstaller_options=%pyinstaller_options% --add-data config;."
)
echo mode: "%m%", dir: "%save_dir%", options: "%pyinstaller_options%"

pip install -r requirements-%m%.txt ^
    && pip install pyinstaller ^
    && pyinstaller %pyinstaller_options% %m%.py ^
    && rmdir /s /q build ^
    && del /q %m%.spec ^
    && copy dist\%m%.exe %save_dir%\ ^
    && rmdir /s /q dist

exit /b