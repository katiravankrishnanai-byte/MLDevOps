pipeline {
  agent any

  environment {
    IMAGE_REPO = "katiravan/mldevops"     // Docker Hub repo
    NAMESPACE  = "mldevopskatir"          // k8s namespace
    APP_NAME   = "mldevops"              // Deployment name AND container name in deployment.yml
    SERVICE    = "mldevops"              // Service name
  }

  options { timestamps() }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        bat 'git --version'
        bat 'docker --version'
        bat 'kubectl version --client=true'
        bat 'git status'
        bat 'git rev-parse HEAD'
      }
    }

    stage('Compute Tags') {
      steps {
        script {
          // Get 7-char git commit safely (no FOR loop, no delayed expansion)
          env.SHORTSHA = bat(returnStdout: true, script: 'git rev-parse --short=7 HEAD').trim()

          // Get git tag if HEAD is exactly at a tag; otherwise blank
          def rel = bat(returnStdout: true, script: '@echo off\r\ngit describe --tags --exact-match 2>nul').trim()
          env.RELTAG = rel
        }
        bat '@echo on\necho SHORTSHA=%SHORTSHA%\necho RELTAG=%RELTAG%'
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
          python -m pytest -q --junitxml=reports\\test-results.xml
          dir reports
        '''
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/test-results.xml', fingerprint: true
        }
      }
    }

    stage('Build Image') {
      steps {
        bat '''
          @echo on
          echo Building image: %IMAGE_REPO%:git-%SHORTSHA%
          docker build -t %IMAGE_REPO%:git-%SHORTSHA% .

          if not "%RELTAG%"=="" (
            echo Applying release tag: %RELTAG%
            docker tag %IMAGE_REPO%:git-%SHORTSHA% %IMAGE_REPO%:%RELTAG%
          ) else (
            echo No release tag. Skipping SemVer tag.
          )
        '''
      }
    }

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            @echo on
            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin

            docker push %IMAGE_REPO%:git-%SHORTSHA%

            if not "%RELTAG%"=="" (
              docker push %IMAGE_REPO%:%RELTAG%
            ) else (
              echo No release tag. Skipping push for SemVer tag.
            )
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

            kubectl apply -f k8s\\namespace.yml
            kubectl apply -f k8s\\deployment.yml
            kubectl apply -f k8s\\service.yml

            echo Setting image to: %IMAGE_REPO%:git-%SHORTSHA%
            kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE_REPO%:git-%SHORTSHA%
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

            kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s
            kubectl -n %NAMESPACE% get pods -o wide
            kubectl -n %NAMESPACE% get svc
          '''
        }
      }
    }

    stage('Smoke Test (/health)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% run curl --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS http://%SERVICE%:8000/health
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
            setlocal EnableDelayedExpansion

            kubectl -n %NAMESPACE% delete pod k6 --ignore-not-found

            kubectl -n %NAMESPACE% create configmap k6-script --from-file=loadtest\\k6.js --dry-run=client -o yaml | kubectl apply -f -

            > k6-pod.yaml (
              echo apiVersion: v1
              echo kind: Pod
              echo metadata:
              echo   name: k6
              echo   namespace: %NAMESPACE%
              echo spec:
              echo   restartPolicy: Never
              echo   containers:
              echo   - name: k6
              echo     image: grafana/k6:latest
              echo     env:
              echo     - name: BASE_URL
              echo       value: "http://%SERVICE%:8000"
              echo     args: ["run","/scripts/k6.js"]
              echo     volumeMounts:
              echo     - name: k6-scripts
              echo       mountPath: /scripts
              echo   volumes:
              echo   - name: k6-scripts
              echo     configMap:
              echo       name: k6-script
            )

            kubectl -n %NAMESPACE% apply -f k6-pod.yaml

            kubectl -n %NAMESPACE% wait --for=condition=Ready pod/k6 --timeout=60s

            rem stream logs (k6 will still run; this returns when container ends)
            kubectl -n %NAMESPACE% logs -f pod/k6

            rem Wait until pod is Completed (Succeeded/Failed)
            set PHASE=
            for /L %%A in (1,1,60) do (
              for /f %%P in ('kubectl -n %NAMESPACE% get pod k6 -o jsonpath^="{.status.phase}" 2^>nul') do set PHASE=%%P
              if /I "!PHASE!"=="Succeeded" goto phase_done
              if /I "!PHASE!"=="Failed"    goto phase_done
              timeout /t 3 /nobreak >nul
            )

            :phase_done
            echo K6 pod phase: !PHASE!

            rem Extract exit code (0=pass). If not terminated yet, value may be blank.
            set K6_EXIT=
            for /f %%E in ('kubectl -n %NAMESPACE% get pod k6 -o jsonpath^="{.status.containerStatuses[0].state.terminated.exitCode}" 2^>nul') do set K6_EXIT=%%E
            echo K6 exit code: !K6_EXIT!

            if not "!K6_EXIT!"=="0" (
              echo ERROR: k6 failed thresholds/tests.
              kubectl -n %NAMESPACE% describe pod k6
              exit /b 1
            )

            kubectl -n %NAMESPACE% delete pod k6 --ignore-not-found
            endlocal
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'k8s/**/*,loadtest/**/*,Dockerfile,Jenkinsfile,requirements.txt,README.md', fingerprint: true
    }
  }
}
