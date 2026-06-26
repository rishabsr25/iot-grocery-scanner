#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include "esp_http_server.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "secrets.h"

// ---- OLED (I2C bus 0 via Wire; camera SCCB uses bus 1 on GPIO26/27) ----
#define OLED_SDA         13
#define OLED_SCL         33
#define OLED_ADDR        0x3C
#define OLED_WIDTH       128
#define OLED_HEIGHT      64

Adafruit_SSD1306 oled(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
bool oledReady = false;

// ---- Camera pins (your confirmed working config) ----
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    32
#define SIOD_GPIO_NUM    26
#define SIOC_GPIO_NUM    27
#define Y2_GPIO_NUM       5
#define Y3_GPIO_NUM      18
#define Y4_GPIO_NUM      19
#define Y5_GPIO_NUM      21
#define Y6_GPIO_NUM      36
#define Y7_GPIO_NUM      39
#define Y8_GPIO_NUM      34
#define Y9_GPIO_NUM      35
#define VSYNC_GPIO_NUM   25
#define HREF_GPIO_NUM    23
#define PCLK_GPIO_NUM    22

#define BUTTON_GPIO      14

httpd_handle_t stream_httpd = NULL;
volatile bool streamingEnabled = true;

static const char* MULTIPART_BOUNDARY = "----ESP32IdentifyBoundary";

#define PART_BOUNDARY "123456789000000000000987654321"
static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  char part_buf[64];

  res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  while (true) {
    if (!streamingEnabled) {
      // Paused — just hold the connection open without sending new frames.
      // The browser keeps displaying whatever the last frame was.
      delay(200);
      continue;
    }

    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed in stream");
      res = ESP_FAIL;
    } else {
      size_t hlen = snprintf(part_buf, 64, STREAM_PART, fb->len);
      if (res == ESP_OK) res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
      if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, hlen);
      if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
      esp_camera_fb_return(fb);
    }
    if (res != ESP_OK) break;
    delay(100);
  }
  return res;
}

bool initOled() {
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED init failed");
    return false;
  }
  oledReady = true;
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);
  oled.println("Ready to scan");
  oled.display();
  return true;
}

void showOledLines(const String& line1, const String& line2) {
  if (!oledReady) {
    return;
  }
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);
  oled.println(line1);
  oled.println(line2);
  oled.display();
}

bool jsonStringField(const String& json, const char* key, String& out) {
  const String needle = String("\"") + key + "\":\"";
  const int start = json.indexOf(needle);
  if (start < 0) {
    return false;
  }
  const int valueStart = start + needle.length();
  const int valueEnd = json.indexOf('"', valueStart);
  if (valueEnd < 0) {
    return false;
  }
  out = json.substring(valueStart, valueEnd);
  return true;
}

bool jsonFirstPrice(const String& json, String& store, float& price) {
  const int pricesIdx = json.indexOf("\"prices\"");
  if (pricesIdx < 0) {
    return false;
  }

  const int storeIdx = json.indexOf("\"store\":", pricesIdx);
  if (storeIdx < 0) {
    return false;
  }
  const int storeStart = json.indexOf('"', storeIdx + 8);
  const int storeEnd = json.indexOf('"', storeStart + 1);
  if (storeStart < 0 || storeEnd < 0) {
    return false;
  }
  store = json.substring(storeStart + 1, storeEnd);

  const int priceIdx = json.indexOf("\"price\":", storeIdx);
  if (priceIdx < 0) {
    return false;
  }
  price = json.substring(priceIdx + 8).toFloat();
  return true;
}

void showIdentifyOnOled(const String& json) {
  String productName;
  String store;
  float price = 0.0f;

  if (!jsonStringField(json, "product", productName)) {
    return;
  }
  if (!jsonFirstPrice(json, store, price)) {
    showOledLines(productName, "");
    return;
  }

  char priceLine[32];
  snprintf(priceLine, sizeof(priceLine), "%s $%.2f", store.c_str(), price);
  showOledLines(productName, priceLine);
}

bool postFrameToIdentifyServer(camera_fb_t* fb) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected — cannot POST identify request");
    return false;
  }

  String partHeader = String("--") + MULTIPART_BOUNDARY + "\r\n";
  partHeader += "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n";
  partHeader += "Content-Type: image/jpeg\r\n\r\n";

  String partFooter = String("\r\n--") + MULTIPART_BOUNDARY + "--\r\n";
  const size_t bodyLen = partHeader.length() + fb->len + partFooter.length();

  uint8_t* body = (uint8_t*)malloc(bodyLen);
  if (!body) {
    Serial.println("Failed to allocate POST body buffer");
    return false;
  }

  memcpy(body, partHeader.c_str(), partHeader.length());
  memcpy(body + partHeader.length(), fb->buf, fb->len);
  memcpy(body + partHeader.length() + fb->len, partFooter.c_str(), partFooter.length());

  HTTPClient http;
  http.setTimeout(15000);

  WiFiClient client;
  if (!http.begin(client, IDENTIFY_URL)) {
    Serial.println("Failed to connect to identify server");
    free(body);
    return false;
  }

  http.addHeader(
    "Content-Type",
    String("multipart/form-data; boundary=") + MULTIPART_BOUNDARY
  );

  Serial.println("POSTing capture to identify server...");
  const int httpCode = http.POST(body, bodyLen);
  free(body);

  if (httpCode > 0) {
    const String response = http.getString();
    Serial.printf("Identify response (%d):\n", httpCode);
    Serial.println(response);
    if (httpCode == HTTP_CODE_OK) {
      showIdentifyOnOled(response);
    }
  } else {
    Serial.printf("Identify POST failed: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
  return httpCode == HTTP_CODE_OK;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;

  httpd_uri_t stream_uri = {
    .uri = "/stream",
    .method = HTTP_GET,
    .handler = stream_handler,
    .user_ctx = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
  }
}

void buttonTask(void* param) {
  (void)param;
  bool lastButtonState = HIGH;

  for (;;) {
    const bool currentButtonState = digitalRead(BUTTON_GPIO);

    // Detect a fresh press: was HIGH, now LOW (INPUT_PULLUP)
    if (currentButtonState == LOW && lastButtonState == HIGH) {
      vTaskDelay(pdMS_TO_TICKS(50)); // debounce
      Serial.println("Button pressed");

      streamingEnabled = false;
      vTaskDelay(pdMS_TO_TICKS(500)); // let stream pause and free the frame buffer

      camera_fb_t* fb = esp_camera_fb_get();
      if (!fb) {
        Serial.println("Camera capture failed");
      } else {
        postFrameToIdentifyServer(fb);
        esp_camera_fb_return(fb);
      }

      streamingEnabled = true;
    }

    lastButtonState = currentButtonState;
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  initOled();

  pinMode(BUTTON_GPIO, INPUT_PULLUP);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QQVGA;  // 160x120
  config.jpeg_quality = 20;
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_DRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return;
  }
  Serial.println("Camera init succeeded!");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());

  startCameraServer();
  Serial.print("Stream ready at: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");
  Serial.println("Press the button to capture and identify a product.");

  xTaskCreatePinnedToCore(
    buttonTask,
    "buttonTask",
    8192,
    NULL,
    1,
    NULL,
    0
  );
}

void loop() {
  vTaskDelay(portMAX_DELAY);
}
