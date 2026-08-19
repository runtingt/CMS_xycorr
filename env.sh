export ARCH=$(uname -a)

if [[ "$ARCH" == *el9* ]]; then
    echo "Sourcing LCG stack for RHEL9"
    source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc11-opt/setup.sh

else
    if [[ "$HOSTNAME" != "portal1-centos7" ]]; then
        echo "sourcing LCG stack for RHEL9"
        # source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-el9-gcc13-opt/setup.sh
        source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc11-opt/setup.sh
        echo "Done!"

    else
        echo "sourcing LCG stack for CENTOS7"
        source /cvmfs/sft.cern.ch/lcg/views/LCG_102rc1/x86_64-centos7-gcc11-opt/setup.sh
        echo "Done!"
    fi
fi

CopyProxy(){
    mkdir -p ~/proxy
    ID=$(id -u)
    cp /tmp/x509up_u$ID ~/proxy/
    echo "proxy copied to ~/proxy/ for using condor."
}


# Check if voms-proxy-info is installed
if ! command -v voms-proxy-info &> /dev/null; then
    echo "voms-proxy-info not found. Please ensure it is installed and available in PATH."
    exit 1
fi

# Get the remaining time of the VOMS proxy
time_left=$(voms-proxy-info --timeleft 2>/dev/null)

# Check if the proxy exists
if [[ $? -ne 0 || -z $time_left ]]; then
    echo "No valid VOMS proxy found."
    time_left=0  # Treat as expired
fi

# Check if time left is sufficient (120 minutes = 7200 seconds)
if [[ $time_left -lt 7200 ]]; then
    echo "VOMS proxy has less than 120 minutes remaining or is not present."
    read -p "Would you like to create a new proxy? (yes/no): " create_proxy
    if [[ $create_proxy =~ ^[Yy]es$ ]]; then
        echo "Creating a new VOMS proxy..."
        voms-proxy-init --voms cms --valid 192:00 -rfc
        if [[ $? -eq 0 ]]; then
            echo "New VOMS proxy successfully created."
            CopyProxy
        else
            echo "Failed to create VOMS proxy. Please check your environment and credentials."
            exit 1
        fi
    else
        echo "Proxy not created. Be aware that tasks requiring a VOMS proxy may fail."
    fi
else
    echo "VOMS proxy is valid. Time left: $time_left seconds."
    CopyProxy
fi

