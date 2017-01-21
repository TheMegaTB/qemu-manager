#!/usr/bin/python
from __future__ import print_function
from pprint import pprint
from subprocess import check_output
from os import path, chmod
import math
import sys
import json
import psutil

HUGEPAGESIZE = 2  # MB (2 * 2048kB)


def called_by_qmsh():
    me = psutil.Process()
    parent = psutil.Process(me.ppid())
    grandparent = psutil.Process(parent.ppid())
    called_from_qm = False
    for arg in grandparent.cmdline():
        if "qemu_manager.sh" in arg:
            called_from_qm = True
    return called_from_qm


def eprint(*args, **kwargs):
    args = (" \033[93m*\033[39m",) + args
    print(*args, file=sys.stderr, **kwargs)


def parse_vm(name):
    vm_path = path.join(path.abspath("./VM"), name)
    with open(path.join(vm_path, 'vm.json')) as data_file:
        vm_config = json.load(data_file)
    vm_config["vm_path"] = vm_path
    return vm_config


modprobed = False


def start_vm(vm_path=None, kvm=True, uefi=None, virtio=True,
             mem=2048, hugepages=False, cores=4, cpu="host", cpu_args=None,
             vga=None, sound=None, usb=None,
             hdd=None, ide_hdd=False, ide=None, scsi=None, pci=None,
             osx=False):
    if vm_path is None:
        exit("ERROR: No VM path passed")

    if hdd is None:
        hdd = []
    if ide is None:
        ide = []
    if scsi is None:
        scsi = []
    if pci is None:
        pci = []
    if usb is None:
        usb = []

    spice = False

    no_defaults = "-serial none -parallel none -no-user-config -nodefaults -nodefconfig "
    additional_options = "-net nic,model=virtio " \
                         "-net vde " \
                         "-machine pc-q35-2.4,accel=kvm,kernel_irqchip=on,mem-merge=off "
    cmdline = "qemu-system-x86_64 "
    drive_id = 0

    f = open('/tmp/qemu_cmdline.sh', 'w')
    print("#!/bin/bash", file=f)

    def unbind_device(dev):
        global modprobed
        if not modprobed:
            print("modprobe vfio-pci", file=f)
            modprobed = True
        print(path.abspath("./unbind_device.sh") + " 0000:" + dev, file=f)

    # Enable KVM
    cmdline += "-enable-kvm " if kvm else ""

    # ------- Base hardware -------

    # Set the RAM allocation
    cmdline += "-m " + str(mem) + " "
    if hugepages:
        cmdline += "-mem-path /dev/hugepages -mem-prealloc "

    # Set the CPU options
    cmdline += "-cpu " + (cpu + "," + cpu_args if cpu_args else cpu) + " "

    # Set the CPU core/socket counts
    cmdline += "-smp " + str(cores) + ",sockets=1,cores=" + str(cores) + ",threads=1 "

    # Enable UEFI
    if uefi:
        uefi = path.join(vm_path, uefi)
        cmdline += "-drive if=pflash,format=raw,readonly,file=" + uefi + " "

    if vga and ":" in vga:
        # Enable VGA passthrough TODO: VGA Passthrough w/ SeaBIOS
        unbind_device(vga)
        cmdline += "-device vfio-pci,host=" + vga + " "
        cmdline += "-vga none -nographic "
    else:
        # Set the VGA emulation
        if uefi:
            vga = "qxl"
            eprint("WARNING: Overridden VGA with qxl since UEFI (and therefore the spice server) is enabled!")
        if vga == "spice":
            vga = "qxl"
            spice = True
        if not osx:
            cmdline += "-vga " + (str(vga) if vga else "none") + " "
        if not osx and vga:
            cmdline += " -usb -usbdevice tablet "

    if spice:
        cmdline += "-spice port=5930,disable-ticketing "
        cmdline += "-device virtio-serial "
        cmdline += "-chardev spicevmc,id=vdagent,name=vdagent "
        cmdline += "-device virtserialport,chardev=vdagent,name=com.redhat.spice.0 "

    # Set the sound device
    if sound:
        cmdline += "-soundhw " + str(sound) + " "

    # Add USB devices
    for usb_device in usb:
        cmdline += "-usbdevice host:" + usb_device + " "

    # Add PCI devices TODO: Rebind those devices to the drivers they had before
    for pci_device in pci:
        cmdline += "-device vfio-pci,host=" + pci_device + " "
        unbind_device(pci_device)

    # ------- Drives -------

    def add_drive(file, d_id, opt=""):
        return "-drive file=\"" + file + "\",id=drive_" + str(d_id) + ",if=none" + ("," + opt + " " if opt != "" else " ")

    if virtio:
        cmdline += "-device virtio-scsi-pci,id=scsi "

    # IDE
    for dvd_image in ide:
        if "GLOBAL/" in dvd_image:
            dvd_image = dvd_image.replace("GLOBAL/", path.abspath("./cd_images") + "/", 1)
        else:
            dvd_image = path.join(vm_path, dvd_image)
        cmdline += add_drive(dvd_image, drive_id) + "-device ide-cd,bus=ide." + str(drive_id) + ",drive=drive_" \
                   + str(drive_id) + " "
        drive_id += 1

    # SCSI
    for dvd_image in scsi:
        if "GLOBAL/" in dvd_image:
            dvd_image = dvd_image.replace("GLOBAL/", path.abspath("./cd_images") + "/", 1)
        else:
            dvd_image = path.join(vm_path, dvd_image)
        cmdline += add_drive(dvd_image, drive_id) + "-device scsi-cd,drive=drive_" + str(drive_id) + " "
        drive_id += 1

    # HDD TODO: w/o Virtio
    for (hdd_file, options) in hdd:
        if not path.isabs(hdd_file):
            hdd_file = path.join(vm_path, hdd_file)
        if ide_hdd:
            cmdline += add_drive(hdd_file, drive_id, options) + "-device ide-drive,bus=ide." + str(drive_id) + \
                       ",drive=drive_" + str(drive_id) + " "
        else:
            cmdline += add_drive(hdd_file, drive_id, options) + "-device scsi-hd,drive=drive_" + str(drive_id) + " "

        drive_id += 1

    # OSX specific functions
    if osx:
        with open('osk-string', 'r') as myfile:
            osk = myfile.read().replace('\n', '')
        cmdline += "-device isa-applesmc,osk='" + osk + \
                   "' -kernel " + path.abspath("enoch_rev2839_boot") + " -smbios type=2 -device usb-kbd -usb -device usb-mouse -monitor stdio "
    else:
        cmdline += no_defaults

    cmdline += additional_options

    print("echo 1 > /sys/module/kvm/parameters/ignore_msrs", file=f)
    if hugepages:
        print("echo " + str(math.ceil(mem / HUGEPAGESIZE / 50) * 50) + " > /proc/sys/vm/nr_hugepages", file=f)
    print(cmdline + additional_options, file=f)
    f.close()
    chmod('/tmp/qemu_cmdline.sh', 0o544)


# -rtc base=localtime \
# -net user,smb=/home/themegatb/ \
# -net nic,model=virtio


def main():
    if not called_by_qmsh():
        eprint("This script may not be called directly.")
        exit(1)
    global HUGEPAGESIZE
    HUGEPAGESIZE = int(sys.argv[1]) / 1024  # Convert kB -> MB
    vm_config = parse_vm(sys.argv[2])
    vm_config.pop("name", None)  # eprint("Loaded " + vm_config.pop("name"))
    start_vm(**vm_config)


if __name__ == '__main__':
    main()
