#!/usr/bin/env bash

# TODO: Argument parsing and quiet flag for qemu

if [ "$EUID" -ne 0 ]; then
    echo -e " \e[91m*\e[39m Please run as root"
    exit
fi

if [ -z "$1" ]; then
    echo -e " \e[91m*\e[39m Please provide a VM name"
    exit
else
    VM=$1
fi

SPICE=0
if [ ! -z "$2" ] && [ "$2" == "--spice" ] || [ "$2" == "-s" ]; then
    SPICE=1
fi

cols=$(tput cols)

function move_before_end_of_line {
    tput el
    for ((n=0;n<$1;n++)); do
        tput cub1
    done
}

function begin {
    echo -e " \e[92m*\e[39m $1 ..."
}

function end {
    move_before_end_of_line 8
    if [ $1 -eq 0 ]; then
        echo -e " \e[1;96m[\e[92m ok \e[96m]\e[39m\e[21m "
    else
        echo -e " \e[1m\e[96m[\e[91m !! \e[96m]\e[39m\e[21m"
    fi
}

function try {
    "$@"
    local status=$?
    if [ ${status} -ne 0 ]; then
        # echo "error with $1" >&2
        end ${status}
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

if [ ${SPICE} -eq 1 ]; then
    begin "Launching spice"
    try sh -c "(sleep 0.5 && i3-msg 'workspace '8: '; exec spicy -f -h 127.0.0.1 -p 5930')" > /dev/null &
    end $?
fi

begin "Starting VM"
cmd=$(./qemu_manager.py ${VM})

#echo ${cmd}
echo -e "\e[90m"
try ${cmd}
end $?

begin "Removing IP forwarding device"
ip link delete tap0
kill ${TAP_PID}
end $?