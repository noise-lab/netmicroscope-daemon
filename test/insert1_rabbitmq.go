package main

import (
	"bufio"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"strconv"
	"time"

	"github.com/streadway/amqp"
)

func failOnError(err error, msg string) {
	if err != nil {
		log.Fatalf("%s: %s", msg, err)
	}
}

func checkEnv(v string, env string) {
	if v == "" {
		log.Fatalf("%s: %s", env, "env variable not present")
	}
}

func tlsClientConfig(caCertPath string, clientCertPath string, clientKeyPath string) *tls.Config {

	caCert, err := ioutil.ReadFile(caCertPath)
	failOnError(err, "caCertPath")
	clientCert, err := ioutil.ReadFile(clientCertPath)
	failOnError(err, "clientCertPath")
	clientKey, err := ioutil.ReadFile(clientKeyPath)
	failOnError(err, "clientKeyPath")

	cfg := new(tls.Config)
	cfg.RootCAs = x509.NewCertPool()
	cfg.RootCAs.AppendCertsFromPEM([]byte(caCert))

	cert, err := tls.X509KeyPair([]byte(clientCert), []byte(clientKey))
	failOnError(err, "X509KeyPair")

	cfg.Certificates = append(cfg.Certificates, cert)

	return cfg
}

func main() {

	user := os.Getenv("RABBITMQ_SSL_USER")
	checkEnv(user, "RABBITMQ_SSL_USER")

	pass := os.Getenv("RABBITMQ_SSL_PASS")
	checkEnv(pass, "RABBITMQ_SSL_PASS")

	host := os.Getenv("RABBITMQ_SSL_HOST")
	checkEnv(host, "RABBITMQ_SSL_HOST")

	portStr := os.Getenv("RABBITMQ_SSL_PORT")
	checkEnv(portStr, "RABBITMQ_SSL_PORT")
	port, err := strconv.Atoi(portStr)
	failOnError(err, "RABBITMQ_SSL_PORT")

	caCertificate := os.Getenv("RABBITMQ_SSL_CACERT") //don't have to be bundled, as this is client
	checkEnv(caCertificate, "RABBITMQ_SSL_CACERT")

	clientCertificate := os.Getenv("RABBITMQ_SSL_CERTFILE")
	checkEnv(clientCertificate, "RABBITMQ_SSL_CERTFILE")

	clientKey := os.Getenv("RABBITMQ_SSL_KEYFILE")
	checkEnv(clientKey, "RABBITMQ_SSL_KEYFILE")

	topic := os.Getenv("RABBITMQ_SSL_TOPIC")
	checkEnv(topic, "RABBITMQ_SSL_TOPIC")

	url := fmt.Sprintf("amqps://%s:%s@%s:%d/", user, pass, host, port)
	//conn, err := amqp.Dial("amqp://guest:guest@localhost:5672/")
	conn, err := amqp.DialTLS(url, tlsClientConfig(caCertificate, clientCertificate, clientKey))
	//tip: convert .pem to .key (rsa encrypted key) via //openssl pkey -in cert/client_key.pem -out cert/client_key.key

	failOnError(err, "Failed to connect to RabbitMQ")
	defer conn.Close()

	ch, err := conn.Channel()
	failOnError(err, "Failed to open a channel")
	defer ch.Close()

	q, err := ch.QueueDeclare(
		topic, // name
		false, // durable
		false, // delete when unused
		false, // exclusive
		false, // no-wait
		nil,   // arguments
	)
	failOnError(err, "Failed to declare a queue")

	f, err := os.Open("insert1_rabbitmq.testjson1.json") // os.OpenFile has more options if you need them
	defer f.Close()
	failOnError(err, "insert1_rabbitmq.testjson1.json")

	fileScanner := bufio.NewScanner(f)
	lines := 0
	for fileScanner.Scan() {
		lines++
	}

	f.Seek(0, io.SeekStart)

	rd := bufio.NewReader(f)

	ind := 0
	for {
		TsStart := int(time.Now().Unix()) - (lines-ind)*5 - 5
		TsEnd := TsStart + 5
		line, err := rd.ReadString('\n')
		if err == io.EOF {
			fmt.Print(line)
			break
		}

		failOnError(err, "ReadLine")
		in := []byte(line)
		var j map[string]interface{}
		if err := json.Unmarshal(in, &j); err != nil {
			panic(err)
		}

		j["Info"].(map[string]interface{})["TsStart"] = TsStart
		j["Info"].(map[string]interface{})["TsEnd"] = TsEnd

		body, err := json.Marshal(j)
		if err != nil {
			panic(err)
		}
		fmt.Printf("Injecting data - TsStart:%d TsEnd:%d\n", TsStart, TsEnd)
		//println(string(out))
		err = ch.Publish(
			"",     // exchange
			q.Name, // routing key
			false,  // mandatory
			false,  // immediate
			amqp.Publishing{
				ContentType: "text/plain",
				Body:        []byte(body),
			})
		ind++
	}

	body := "Hello World!"
	err = ch.Publish(
		"",     // exchange
		q.Name, // routing key
		false,  // mandatory
		false,  // immediate
		amqp.Publishing{
			ContentType: "text/plain",
			Body:        []byte(body),
		})
	log.Printf(" [x] Sent %s", body)
	failOnError(err, "Failed to publish a message")
}

/* from original example: https://github.com/streadway/amqp/blob/master/tls_test.go
const caCert = `
-----BEGIN CERTIFICATE-----
MIICxjCCAa6gAwIBAgIJANWuMWMQSxvdMA0GCSqGSIb3DQEBBQUAMBMxETAPBgNV
BAMTCE15VGVzdENBMB4XDTE0MDEyNzE5NTIyMloXDTI0MDEyNTE5NTIyMlowEzER
MA8GA1UEAxMITXlUZXN0Q0EwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIB
AQDBsIrkW4ob9Z/gzR2/Maa2stbutry6/vvz8eiJwIKIbaHGwqtFOUGiWeKw7H76
IH3SjTAhNQY2hoKPyH41D36sDJkYBRyHFJTK/6ffvOhpyLnuXJAnoS62eKPSNUAx
5i/lkHj42ESutYAH9qbHCI/gBm9G4WmhGAyA16xzC1n07JObl6KFoY1PqHKl823z
mvF47I24DzemEfjdwC9nAAX/pGYOg9FA9nQv7NnhlsJMxueCx55RNU1ADRoqsbfE
T0CQTOT4ryugGrUp9J4Cwen6YbXZrS6+Kff5SQCAns0Qu8/bwj0DKkuBGLF+Mnwe
mq9bMzyZPUrPM3Gu48ao8YAfAgMBAAGjHTAbMAwGA1UdEwQFMAMBAf8wCwYDVR0P
BAQDAgEGMA0GCSqGSIb3DQEBBQUAA4IBAQCBwXGblRxIEOlEP6ANZ1C8AHWyG8lR
CQduFclc0tmyCCz5fnyLK0aGu9LhXXe6/HSKqgs4mJqeqYOojdjkfOme/YdwDzjK
WIf0kRYQHcB6NeyEZwW8C7subTP1Xw6zbAmjvQrtCGvRM+fi3/cs1sSSkd/EoRk4
7GM9qQl/JIIoCOGncninf2NQm5YSpbit6/mOQD7EhqXsw+bX+IRh3DHC1Apv/PoA
HlDNeM4vjWaBxsmvRSndrIvew1czboFM18oRSSIqAkU7dKZ0SbC11grzmNxMG2aD
f9y8FIG6RK/SEaOZuc+uBGXx7tj7dczpE/2puqYcaVGwcv4kkrC/ZuRm
-----END CERTIFICATE-----
`

const clientCert = `
-----BEGIN CERTIFICATE-----
MIIC4jCCAcqgAwIBAgIBAjANBgkqhkiG9w0BAQUFADATMREwDwYDVQQDEwhNeVRl
c3RDQTAeFw0xNDAxMjcxOTUyMjNaFw0yNDAxMjUxOTUyMjNaMCUxEjAQBgNVBAMT
CTEyNy4wLjAuMTEPMA0GA1UEChMGY2xpZW50MIIBIjANBgkqhkiG9w0BAQEFAAOC
AQ8AMIIBCgKCAQEAu7LMqd+agoH168Bsi0WJ36ulYqDypq+GZPF7uWOo2pE0raKH
B++31/hjnkt6yC5kLKVZZ0EfolBa9q4Cy6swfGaEMafy44ZCRneLnt1azL1N6Kfz
+U0KsOqyQDoMxYJG1gVTEZN19/U/ew2eazcxKyERI3oGCQ4SbpkxBTbfxtAFk49e
xIB3obsuMVUrmtXE4FkUkvG7NgpPUgrhp0yxYpj9zruZGzGGT1zNhcarbQ/4i7It
ZMbnv6pqQWtYDgnGX2TDRcEiXGeO+KrzhfpTRLfO3K4np8e8cmTyXM+4lMlWUgma
KrRdu1QXozGqRs47u2prGKGdSQWITpqNVCY8fQIDAQABoy8wLTAJBgNVHRMEAjAA
MAsGA1UdDwQEAwIHgDATBgNVHSUEDDAKBggrBgEFBQcDAjANBgkqhkiG9w0BAQUF
AAOCAQEAhCuBCLznPc4O96hT3P8Fx19L3ltrWbc/pWrx8JjxUaGk8kNmjMjY+/Mt
JBbjUBx2kJwaY0EHMAfw7D1f1wcCeNycx/0dyb0E6xzhmPw5fY15GGNg8rzWwqSY
+i/1iqU0IRkmRHV7XCF+trd2H0Ec+V1Fd/61E2ccJfOL5aSAyWbMCUtWxS3QMnqH
FBfKdVEiY9WNht5hnvsXQBRaNhowJ6Cwa7/1/LZjmhcXiJ0xrc1Hggj3cvS+4vll
Ew+20a0tPKjD/v/2oSQL+qkeYKV4fhCGkaBHCpPlSJrqorb7B6NmPy3nS26ETKE/
o2UCfZc5g2MU1ENa31kT1iuhKZapsA==
-----END CERTIFICATE-----
`

const clientKey = `
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAu7LMqd+agoH168Bsi0WJ36ulYqDypq+GZPF7uWOo2pE0raKH
B++31/hjnkt6yC5kLKVZZ0EfolBa9q4Cy6swfGaEMafy44ZCRneLnt1azL1N6Kfz
+U0KsOqyQDoMxYJG1gVTEZN19/U/ew2eazcxKyERI3oGCQ4SbpkxBTbfxtAFk49e
xIB3obsuMVUrmtXE4FkUkvG7NgpPUgrhp0yxYpj9zruZGzGGT1zNhcarbQ/4i7It
ZMbnv6pqQWtYDgnGX2TDRcEiXGeO+KrzhfpTRLfO3K4np8e8cmTyXM+4lMlWUgma
KrRdu1QXozGqRs47u2prGKGdSQWITpqNVCY8fQIDAQABAoIBAGSEn3hFyEAmCyYi
2b5IEksXaC2GlgxQKb/7Vs/0oCPU6YonZPsKFMFzQx4tu+ZiecEzF8rlJGTPdbdv
fw3FcuTcHeVd1QSmDO4h7UK5tnu40XVMJKsY6CXQun8M13QajYbmORNLjjypOULU
C0fNueYoAj6mhX7p61MRdSAev/5+0+bVQQG/tSVDQzdngvKpaCunOphiB2VW2Aa0
7aYPOFCoPB2uo0DwUmBB0yfx9x4hXX9ovQI0YFou7bq6iYJ0vlZBvYQ9YrVdxjKL
avcz1N5xM3WFAkZJSVT/Ho5+uTbZx4RrJ8b5T+t2spOKmXyAjwS2rL/XMAh8YRZ1
u44duoECgYEA4jpK2qshgQ0t49rjVHEDKX5x7ElEZefl0rHZ/2X/uHUDKpKj2fTq
3TQzHquiQ4Aof7OEB9UE3DGrtpvo/j/PYxL5Luu5VR4AIEJm+CA8GYuE96+uIL0Z
M2r3Lux6Bp30Z47Eit2KiY4fhrWs59WB3NHHoFxgzHSVbnuA02gcX2ECgYEA1GZw
iXIVYaK07ED+q/0ObyS5hD1cMhJ7ifSN9BxuG0qUpSigbkTGj09fUDS4Fqsz9dvz
F0P93fZvyia242TIfDUwJEsDQCgHk7SGa4Rx/p/3x/obIEERk7K76Hdg93U5NXhV
NvczvgL0HYxnb+qtumwMgGPzncB4lGcTnRyOfp0CgYBTIsDnYwRI/KLknUf1fCKB
WSpcfwBXwsS+jQVjygQTsUyclI8KResZp1kx6DkVPT+kzj+y8SF8GfTUgq844BJC
gnJ4P8A3+3JoaH6WqKHtcUxICZOgDF36e1CjOdwOGnX6qIipz4hdzJDhXFpSSDAV
CjKmR8x61k0j8NcC2buzgQKBgFr7eo9VwBTvpoJhIPY5UvqHB7S+uAR26FZi3H/J
wdyM6PmKWpaBfXCb9l8cBhMnyP0y94FqzY9L5fz48nSbkkmqWvHg9AaCXySFOuNJ
e68vhOszlnUNimLzOAzPPkkh/JyL7Cy8XXyyNTGHGDPXmg12BTDmH8/eR4iCUuOE
/QD9AoGBALQ/SkvfO3D5+k9e/aTHRuMJ0+PWdLUMTZ39oJQxUx+qj7/xpjDvWTBn
eDmF/wjnIAg+020oXyBYo6plEZfDz3EYJQZ+3kLLEU+O/A7VxCakPYPwCr7N/InL
Ccg/TVSIXxw/6uJnojoAjMIEU45NoP6RMp0mWYYb2OlteEv08Ovp
-----END RSA PRIVATE KEY-----
`
*/
