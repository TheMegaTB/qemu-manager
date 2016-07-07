for dev in "0000:00:1d.0"
do
	#while [[ ! -e "/sys/bus/pci/drivers/nvidia/${dev}" ]]
	#do
		vendor=$(cat /sys/bus/pci/devices/${dev}/vendor)
		device=$(cat /sys/bus/pci/devices/${dev}/device)

		echo "removing ${dev} vendor+device from vfio-pci id list"
		echo "${vendor} ${device}" | tee \
			"/sys/bus/pci/drivers/vfio-pci/remove_id"
		sleep 0.1

		echo "hot remove pci device at ${dev}"
		echo 1 | tee "/sys/bus/pci/devices/${dev}/remove"
		while [[ -e "/sys/bus/pci/devices/${dev}" ]]
		do
			sleep 0.1
		done

		echo "rescan pci bus to rediscover ${dev}"
		echo 1 | tee "/sys/bus/pci/rescan"
		while [[ ! -e "/sys/bus/pci/devices/${dev}" ]]
		do
			sleep 0.1
		done

		sleep 0.5
	#done

	echo "pci device at ${dev} is bound to nvidia"
done
