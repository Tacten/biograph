Before starting make sure you have created an a normal Patient Appointment & continue by creating an Imaging Appointment, don’t forget to select an Observation template with type Imaging, if you can’t find please create an Observation template with type Imaging, no other fields are mandatory.

Now you can connect to the server and run the modality simulator once the bridge is also turned on.

Connect to the nucleus server (IP: 31.xx.xx.xx)

```bash
su hm
cd ~
```

Open two terminal with the same working directory (/home/hm)

In one terminal run the below command to start the Marley RIS Bridge

```bash
cd marley_ris_bridge/
sudo /home/user/marley_ris_bridge/env/bin/python -m app MARLEY-SCP --host 0.0.0.0 -p 104
#enter the password for user hm
```

In the second terminal run the following commands to start the Marley Modality Simulator

```bash
cd marley_modality_simulator
source env/bin/activate
python -m marley_modality.cli -d
#Continue the program by following the instructions
#Select the previously created Imaging Appointment by entering the serial number associated with it in the terminal
#Continue by pressing 'Y'
```