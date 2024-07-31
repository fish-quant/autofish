String serial_InBytes;


// Define pins
int TTL_start_OUT = 12;
int TTL_finished_IN = 10;
int val_TTL_finished_IN;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(TTL_start_OUT, OUTPUT);
  pinMode(TTL_finished_IN, INPUT);

  Serial.begin(9600);
  Serial.setTimeout(1000);
  
  // TTL signal for debugging
  pinMode(7, OUTPUT);
  pinMode(8, OUTPUT);

}
void loop() {
  
  // TTL signal for debugging (pin 8 can be used to simulate incoming TTL)
  digitalWrite(7, HIGH); 
  digitalWrite(8, LOW); 
  

  if (Serial.available() > 0){

    /*
    // DEBUGGIN : print TTL signal
    val_TTL_in = digitalRead(TTL_in);   // read the input pin
    Serial.println(val_TTL_in);
    delay(10);
    */

    // Read from serial port
    serial_InBytes = Serial.readStringUntil('\n');
    //Serial.println(InBytes);
    
    // Start acquisition
    if (serial_InBytes == "start"){
      Serial.println("Sending TTL trigger to launch acquisition");
      digitalWrite(TTL_start_OUT, HIGH); 
      digitalWrite(LED_BUILTIN, HIGH);

      // Wait for trigger that acquisition is done
      val_TTL_finished_IN = 0;
      while (val_TTL_finished_IN==0) {
        val_TTL_finished_IN = digitalRead(TTL_finished_IN);   // read the input pin
        Serial.println(val_TTL_finished_IN);
        delay(500);
      }

      // Signal received that acquisition is finished
      Serial.println("finished");
      digitalWrite(TTL_start_OUT, LOW);
      digitalWrite(LED_BUILTIN, LOW);
    }

    // Unknown command
    else{
      Serial.println("Unknown command: " + serial_InBytes);
    }
  
  delay(500);
  
  }
}

