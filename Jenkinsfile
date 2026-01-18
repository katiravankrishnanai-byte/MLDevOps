

pipeline {
  agent any

    tools {
  git 'Default'
  }

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
      env.SHORTSHA = bat(returnStdout: true, script: '@echo off\r\ngit rev-parse --short=7 HEAD').trim()

      def s = bat(returnStatus: true, script: '@echo off\r\ngit describe --tags --exact-match 1> .reltag.txt 2>nul')
      env.RELTAG = (s == 0) ? readFile('.reltag.txt').trim() : ''
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
    script {
      if (!(env.SHORTSHA ==~ /^[0-9a-f]{7}$/)) {
        error("SHORTSHA invalid. Expected 7-hex, got: '${env.SHORTSHA}'")
      }
      if (env.RELTAG && !(env.RELTAG ==~ /^[0-9A-Za-z._-]+$/)) {
        error("RELTAG invalid. Got: '${env.RELTAG}'")
      }
    }

    bat '''
      @echo on
      echo Building image: "%IMAGE_REPO%:git-%SHORTSHA%"
      docker build -t "%IMAGE_REPO%:git-%SHORTSHA%" .

      if not "%RELTAG%"=="" (
        echo Applying release tag: %RELTAG%
        docker tag "%IMAGE_REPO%:git-%SHORTSHA%" "%IMAGE_REPO%:%RELTAG%"
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

        rem ---- Clean up any previous run ----
        kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
        kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found

        rem ---- Create/Update ConfigMap with k6 script ----
        kubectl -n %NAMESPACE% create configmap k6-script --from-file=loadtest\\k6.js --dry-run=client -o yml | kubectl apply -f -

        rem ---- Write k6 Job manifest ----
        > k6-job.yml (
          echo apiVersion: batch/v1
          echo kind: Job
          echo metadata:
          echo   name: k6
          echo   namespace: %NAMESPACE%
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
          echo         image: grafana/k6:latest
          echo         env:
          echo         - name: BASE_URL
          echo           value: "http://%SERVICE%:8000"
          echo         args: ["run","/scripts/k6.js"]
          echo         volumeMounts:
          echo         - name: k6-scripts
          echo           mountPath: /scripts
          echo       volumes:
          echo       - name: k6-scripts
          echo         configMap:
          echo           name: k6-script
        )

        rem ---- Apply Job ----
        kubectl -n %NAMESPACE% apply -f k6-job.yml

        rem ---- Wait until Job completes (kubectl wait fix) ----
        kubectl -n %NAMESPACE% wait --for=condition=complete job/k6 --timeout=300s
        if errorlevel 1 (
          echo ERROR: k6 job did not complete within timeout.
          kubectl -n %NAMESPACE% describe job k6
          kubectl -n %NAMESPACE% get pods -l job-name=k6 -o wide
          kubectl -n %NAMESPACE% logs -l job-name=k6 --all-containers=true --tail=-1
          exit /b 1
        )

        rem ---- Print logs (after completion) ----
        kubectl -n %NAMESPACE% logs -l job-name=k6 --all-containers=true --tail=-1

        rem ---- Determine pass/fail from Job status ----
        set SUCCEEDED=
        for /f "delims=" %%S in ('kubectl -n %NAMESPACE% get job k6 -o jsonpath^="{.status.succeeded}" 2^>nul') do set SUCCEEDED=%%S
        set FAILED=
        for /f "delims=" %%F in ('kubectl -n %NAMESPACE% get job k6 -o jsonpath^="{.status.failed}" 2^>nul') do set FAILED=%%F

        if "%SUCCEEDED%"=="1" (
          echo K6 job succeeded.
        ) else (
          echo ERROR: K6 job failed. succeeded=%SUCCEEDED% failed=%FAILED%
          kubectl -n %NAMESPACE% describe job k6
          kubectl -n %NAMESPACE% get pods -l job-name=k6 -o wide
          kubectl -n %NAMESPACE% logs -l job-name=k6 --all-containers=true --tail=-1
          exit /b 1
        )

        rem ---- Cleanup (optional) ----
        kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
        kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found

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
