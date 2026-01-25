// Jenkinsfile (stable: MODEL_PATH fixed, smoke /predict payload fixed, k6 wait fixed)
pipeline {
  agent any

  environment {
    IMAGE_REPO = "katiravan/mldevops"
    NS = "mldevopskatir"
    APP = "mldevops"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        bat 'git --version'
        bat 'docker --version'
        bat 'kubectl version --client=true'
      }
    }

    stage('Compute Tags') {
      steps {
        script {
          env.SHORTSHA = bat(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          env.IMG_GIT = "${env.IMAGE_REPO}:git-${env.SHORTSHA}"
        }
        bat 'echo SHORTSHA=%SHORTSHA%'
        bat 'echo IMG_GIT=%IMG_GIT%'
      }
    }

    stage('QA (Unit Tests)') {
      steps {
        bat '''
          @echo on
          python --version
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest

          if not exist reports mkdir reports

          REM Ensure the app loads the artifact in QA runtime too
          set MODEL_PATH=%WORKSPACE%\\models\\model.joblib

          python -m pytest -q --junitxml=reports\\test-results.xml
        '''
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/test-results.xml', fingerprint: true
          bat 'rmdir /s /q reports 2>nul'
        }
      }
    }

    stage('Build Image') {
      steps {
        bat '''
          @echo on
          echo Building image: "%IMG_GIT%"
          docker build -t "%IMG_GIT%" .
        '''
      }
    }

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'docker-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            @echo on
            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin
            docker push "%IMG_GIT%"
          '''
        }
      }
    }

    stage('Deploy to Kubernetes (Apply + Set Image)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl apply -f k8s\\namespace.yaml
            kubectl apply -f k8s\\deployment.yaml
            kubectl apply -f k8s\\service.yaml

            kubectl -n %NS% set image deployment/%APP% %APP%=%IMG_GIT%
          '''
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%
            kubectl -n %NS% rollout status deployment/%APP% --timeout=180s
            kubectl -n %NS% get pods -o wide
            kubectl -n %NS% get svc
          '''
        }
      }
    }

    stage('Smoke Test (/health + /predict)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%
            set POD=curl-%BUILD_NUMBER%
            kubectl -n %NS% delete pod %POD% --ignore-not-found

            echo ===== smoke test /health =====
            kubectl -n %NS% run %POD% --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS http://%APP%:8000/health || exit /b 1

            echo ===== smoke test /predict =====
            kubectl -n %NS% run %POD% --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS -X POST http://%APP%:8000/predict ^
              -H "Content-Type: application/json" ^
              -d "{\\"Acceleration\\":5.0,\\"TopSpeed_KmH\\":180,\\"Range_Km\\":420,\\"Battery_kWh\\":75,\\"Efficiency_WhKm\\":170,\\"FastCharge_kW\\":150,\\"Seats\\":5,\\"PriceEuro\\":45000,\\"PowerTrain\\":\\"AWD\\"}" ^
              || exit /b 1
          '''
        }
      }
    }

    stage('Load Test (k6)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%
            set JOB=k6
            set CM=k6-script
            set SCRIPT=%WORKSPACE%\\loadtest\\k6.js

            if not exist "%SCRIPT%" (
              echo ERROR: k6 script not found at path: %SCRIPT%
              dir /s "%WORKSPACE%\\loadtest"
              exit /b 1
            )

            kubectl -n %NS% delete job %JOB% --ignore-not-found
            kubectl -n %NS% delete configmap %CM% --ignore-not-found

            kubectl -n %NS% create configmap %CM% --from-file=k6.js="%SCRIPT%" || exit /b 1

            (
              echo apiVersion: batch/v1
              echo kind: Job
              echo metadata:
              echo   name: %JOB%
              echo   namespace: %NS%
              echo spec:
              echo   backoffLimit: 0
              echo   template:
              echo     metadata:
              echo       labels:
              echo         app: k6
              echo     spec:
              echo       restartPolicy: Never
              echo       containers:
              echo       - name: k6
              echo         image: grafana/k6:0.48.0
              echo         env:
              echo         - name: BASE_URL
              echo           value: "http://%APP%:8000"
              echo         volumeMounts:
              echo         - name: script
              echo           mountPath: /scripts
              echo         command: ["k6","run","/scripts/k6.js"]
              echo       volumes:
              echo       - name: script
              echo         configMap:
              echo           name: %CM%
            ) > k6-job.yaml

            kubectl apply -f k6-job.yaml || exit /b 1

            echo ===== k6: wait complete OR failed =====
            kubectl -n %NS% wait --for=condition=complete job/%JOB% --timeout=240s || ^
            kubectl -n %NS% wait --for=condition=failed job/%JOB% --timeout=240s

            kubectl -n %NS% get job %JOB% -o wide

            echo ===== k6 logs =====
            kubectl -n %NS% logs -l app=k6 --tail=-1

            echo ===== cleanup k6 resources =====
            kubectl -n %NS% delete job %JOB% --ignore-not-found
            kubectl -n %NS% delete configmap %CM% --ignore-not-found
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'k6-job.yaml', allowEmptyArchive: true
    }
  }
}
