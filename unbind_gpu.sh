#for dev in "0000:03:00.0" "0000:03:00.1"
#do
#	if [[ ! -e "/sys/bus/pci/drivers/vfio-pci/${dev}"
#		&& -e "/sys/bus/pci/devices/${dev}/driver" ]]
#	then
#		echo "unbinding pci addr from driver"
#
#		echo "${dev}" | tee "/sys/bus/pci/drivers/nvidia/unbind"
#
#		while [ -e "/sys/bus/pci/drivers/nvidia/${dev}" ]
#		do
#			sleep 0.1
#		done
#	fi
#done

#for dev in "0000:03:00.0" "0000:03:00.1"
#do
#	if [[ ! -e "/sys/bus/pci/drivers/vfio-pci/${dev}" ]]
#	then
#		echo "binding pci addr to vfio-pci"
#
#		vendor=$(cat "/sys/bus/pci/devices/${dev}/vendor")
#		device=$(cat "/sys/bus/pci/devices/${dev}/device")
#		echo "${vendor} ${device}" \
#			| tee "/sys/bus/pci/drivers/vfio-pci/new_id"
#	fi
#done

#!/bin/bash

modprobe vfio-pci

for dev in "$@"; do
        vendor=$(cat /sys/bus/pci/devices/$dev/vendor)
        device=$(cat /sys/bus/pci/devices/$dev/device)
        if [ -e /sys/bus/pci/devices/$dev/driver ]; then
                echo $dev > /sys/bus/pci/devices/$dev/driver/unbind
        fi
        echo $vendor $device > /sys/bus/pci/drivers/vfio-pci/new_id
done
