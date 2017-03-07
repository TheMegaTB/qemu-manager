#!/usr/bin/env bash

if [ "$EUID" -ne 0 ]; then
    if [ ! -z "$DISPLAY" ] && hash gksudo 2>/dev/null; then
        gksudo --preserve-env --message "QEMU Manager wants to start a VM and requires root permission to do so." "$0 $@"
    fi
    if [ $? -ne 0 ] || [ -z "$DISPLAY" ] || ! hash gksudo 2>/dev/null; then
        echo -e " \e[91m*\e[39m Please run as root"
    fi
    exit
fi

function print_help() {
    echo -e "$(basename "$0") [-h] [-s] [-q(q)] [-t] VM -- manager for various tasks regarding QEMU based virtual machines.\n
\n
where:\n
    --help       [-h]   show this help text\n
    --spicey     [-s]   launches the spicey client automagically\n
    --sdl        [-l]   override vga and PCI passthrough\n
    --quiet      [-q]   mutes the QEMU output including errors\n
    --very-quiet [-qq]  mutes everything\n
    --test       [-t]   generate cmdline and display it. May be the last parameter passed"
}

cols=$(tput cols)
hugepagesize=$(sed -n 's/Hugepagesize://p' /proc/meminfo | awk '{print $1}')

while [[ $# > 1 ]]; do
    key="$1"
    case ${key} in
        -q|--quiet)
            QUIET=1
            #shift # past argument
            ;;
        -qq|--very-quiet)
            QUIET=2
            #shift # past argument
            ;;
        -s|--spicey)
            SPICE=1
            #shift # past argument
            ;;
        -l|--sdl)
            SDL=1
            ;;
        -h|--help|-help)
            print_help
            exit 0
            ;;
        -t|--test)
            ./qemu_manager.py ${hugepagesize} $2
            cat /tmp/qemu_cmdline.sh | less
            exit 0
            ;;
        *)
            # unknown option
            ;;
    esac
    shift # past argument or value
done

if [ -z "$1" ]; then
    echo -e " \e[91m*\e[39m Please provide a VM name"
    exit
fi

function move_before_end_of_line {
    tput el
    for ((n=0;n<$1;n++)); do
        tput cub1
    done
}

function begin {
    if [ ! -z ${QUIET} ] && [ ${QUIET} -ne 2 ] || [ -z ${QUIET} ]; then
        echo -e " \e[92m*\e[39m $1 ..."
    fi
}

function end {
    if [ ! -z ${QUIET} ] && [ ${QUIET} -ne 2 ] || [ -z ${QUIET} ]; then
        move_before_end_of_line 8
        if [ $1 -eq 0 ]; then
            echo -e " \e[1;96m[\e[92m ok \e[96m]\e[39m\e[21m "
        else
            echo -e " \e[1m\e[96m[\e[91m !! \e[96m]\e[39m\e[21m"
        fi
    fi
}

function try {
    if [ -z ${QUIET} ]; then
        "$@"
    else
        "$@" >/dev/null 2>&1
    fi
    local status=$?
    if [ ${status} -ne 0 ]; then
        # echo "error with $1" >&2
        end ${status}
        killall vde_switch >/dev/null 2>&1
        exit ${status}
    fi
    return ${status}
}

begin "Exporting PulseAudio driver"
try export QEMU_PA_SAMPLES=128
try export QEMU_AUDIO_DRV="pa"
end $?

begin "Setting up IP forwarding"
vde_switch -tap tap0 -mod 660 -group kvm >/dev/null 2>&1 &
TAP_PID=$!
while ! ip a | grep -F "tap0" > /dev/null; do
    sleep 0.5
done
try ip addr add 10.0.2.1/24 dev tap0
try ip link set dev tap0 up
try sysctl -w net.ipv4.ip_forward=1 > /dev/null
try iptables -t nat -A POSTROUTING -s 10.0.2.0/24 -j MASQUERADE
end $?

if [ ! -z ${SPICE} ]; then
    begin "Launching spice"
    try sh -c "(sleep 0.5 && i3-msg 'workspace '8: '; exec spicy --spice-preferred-compression=off -f -h 127.0.0.1 -p 5930')" > /dev/null &
    end $?
fi

begin "Starting VM"
try ./qemu_manager.py ${hugepagesize} $1 ${SDL}

echo -e "\e[90m"
try /tmp/qemu_cmdline.sh
end $?

begin "Removing IP forwarding device"
kill ${TAP_PID}
end $?
