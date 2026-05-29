Program Overview:
The program included works to process the data received from the .DAT files output by the VersaLAB
into a .CSV file readable by the Origin 2021 program. The included program has [] different 
modes that each operate on a different type of .DAT file from VersaLAB. Included below is a general 
explanation of the way that each of the programs operates and instructions for using them. 

VSM Hysteresis:
This program will convert the .DAT files sent by VersaLAB to a CSV file that can be read by the 
Origin 2021 program to produce graphs. The final file output by the Orange program will include 
an array with rows containing the Temperature (K), Magnetic Field (T), and Magnetization (A*m^2/kg) 
of a given reading.

VSM Hysteresis Data Processing Instructions:
1) After opening the Orange program select the VSM Hysteresis Data Processing Program choose the 
VSM Hysteresis option.
2) After the window opens select the browse option in the upper right corner and navigate to the 
.DAT file you would like to convert and select it. After selecting the file the bar to the left of the 
Browse button will display the file path to your given file. 
3) In the bar below the file path bar input the temperatures separated by commas you would like to separate 
temperature for. Each of these temperatures will have a tolerance of +/- 1K. For example, inputting the values
50, 150, 300 will output a CSV file containing data for a range of 49-51K, 149-151K, and 299-301K.
4) Click the Convert & Save button on the bottom of the window to start the program which will begin to 
Convert the inputed .DAT file into a filtered CSV file. After the program is finished a pop-up will appear
with the destination of the file. On the bottom of the window, text will also appear containing information on
the mass of the sample, the number of rows contained in the CSV file, and the location of the saved CSV file
5) Navigate to the CSV file and drag it onto an open workbook in the Origin 2021 Program.